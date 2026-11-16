"""Fail-closed public-source adapters; never synthesize missing observations."""
from io import BytesIO, StringIO
from datetime import datetime, timezone
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup

BETA_URL='https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls'
SPREAD_URL='https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.htm'
TAX_URL='https://sdmx.oecd.org/public/rest/v1/data/OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,2.0/.'
BONDS_URL='https://tradingeconomics.com/bonds'


def get(url, **kwargs):
    r=requests.get(url, timeout=(10,45), headers={'User-Agent':'Mozilla/5.0 (public academic cost-of-capital calculator)', **kwargs}, params=None)
    r.raise_for_status()
    return r


def meta(url, observation='Not published / not parsed'):
    return dict(source=url, observation_date=observation,
                retrieved_utc=datetime.now(timezone.utc).isoformat())


def betas():
    raw=get(BETA_URL).content
    book=pd.ExcelFile(BytesIO(raw))
    header=None
    for sheet_name in book.sheet_names:
        sheet=pd.read_excel(book,sheet_name=sheet_name,header=None)
        header=next((i for i,row in sheet.iterrows() if any(str(v).strip().lower()=='industry name' for v in row)),None)
        if header is not None: break
    if header is None: raise ValueError('Industry header not found in Damodaran workbook.')
    df=pd.read_excel(book,sheet_name=sheet_name,header=header)
    cols={str(c).strip().lower():c for c in df.columns}
    # Exact unlevered beta: do not silently use cash-adjusted beta.
    if 'unlevered beta' not in cols: raise ValueError('Exact Unlevered beta column missing.')
    out=df[[cols['industry name'],cols['unlevered beta']]].copy()
    out.columns=['industry','beta']
    out['beta']=pd.to_numeric(out.beta,errors='coerce')
    out=out.dropna().query('beta >= 0')
    out=out[~out.industry.astype(str).str.contains('Total Market',case=False)]
    date_rows=[row for row in sheet.iloc[:header].values if any('date updated' in str(v).lower() for v in row)]
    dates=' | '.join(' '.join(str(v) for v in row if pd.notna(v)) for row in date_rows)
    if out.empty: raise ValueError('No valid industry observations.')
    return out,meta(BETA_URL,dates or 'Workbook date unavailable')


def spread():
    soup=BeautifulSoup(get(SPREAD_URL).text,'html.parser')
    # First large-firm panel: rating cell followed immediately by its spread.
    for row in soup.select('tr'):
        cells=[c.get_text(' ',strip=True) for c in row.find_all(['td','th'],recursive=False)]
        for i,c in enumerate(cells[:4]):
            if re.fullmatch(r'Baa2\s*/\s*BBB',c) and i+1<len(cells):
                m=re.fullmatch(r'([\d.]+)\s*%',cells[i+1])
                if m: return float(m.group(1))/100,meta(SPREAD_URL)
    raise ValueError('Large-firm Baa2/BBB row not found; manual entry required.')


def taxes():
    # Retain all coded dimensions; user confirms the selected tax definition.
    r=get(TAX_URL, Accept='text/csv')
    df=pd.read_csv(StringIO(r.text))
    if not {'REF_AREA','TIME_PERIOD','OBS_VALUE'}.issubset(df.columns):
        raise ValueError('OECD SDMX schema changed; upload an OECD CSV or enter tax manually.')
    return df,meta(r.url,'Select latest year within the confirmed standard combined tax series')


def tax_series(df):
    """Expose series instead of guessing among central/combined/SME rates."""
    ignored={'STRUCTURE','STRUCTURE_ID','STRUCTURE_NAME','ACTION','REF_AREA','Reference area',
             'TIME_PERIOD','Time period','OBS_VALUE','Observation value','OBS_STATUS','Observation status',
             'DECIMALS','Decimals','UNIT_MULT','Unit multiplier'}
    dims=[c for c in df.columns if c not in ignored and df[c].nunique(dropna=False)>1]
    out=df.copy()
    out['_series']=out[dims].fillna('').astype(str).agg(' | '.join,axis=1) if dims else 'Only series (confirm definition)'
    return out


def bonds():
    html=get(BONDS_URL).text
    soup=BeautifulSoup(html,'html.parser')
    records=[]
    for table in soup.select('table'):
        headers=[c.get_text(' ',strip=True).lower() for c in table.select('thead th')]
        # Never assume the first numeric column is the last observed yield.
        idx=next((i for i,h in enumerate(headers) if h in ('yield','last','actual')),None)
        if idx is None: continue
        date_idx=next((i for i,h in enumerate(headers) if h in ('date','time')),None)
        for row in table.select('tbody tr'):
            cells=row.find_all(['td','th'],recursive=False)
            link=row.find('a',href=re.compile('/government-bond-yield'))
            if not link or idx>=len(cells): continue
            value=cells[idx].get_text(' ',strip=True).replace('%','').replace(',','')
            try: value=float(value)/100
            except ValueError: continue
            if not -0.2<value<1: continue
            slug=link['href'].strip('/').split('/')[0]
            records.append(dict(country=link.get_text(' ',strip=True),slug=slug,yield_rate=value,
                                observation_date=cells[date_idx].get_text(' ',strip=True) if date_idx is not None and date_idx<len(cells) else 'Unavailable',
                                source='https://tradingeconomics.com/'+slug+'/government-bond-yield'))
    if not records: raise ValueError('Trading Economics returned no recognizable 10-year yield table (possibly blocked or dynamic). Use sourced manual yields.')
    return pd.DataFrame(records).drop_duplicates('slug'),meta(BONDS_URL)
