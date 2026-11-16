"""Fail-closed public-source adapters; never synthesize missing observations."""
from io import BytesIO, StringIO
from datetime import datetime, timezone
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup

BETA_URL='https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls'
SPREAD_URL='https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html'
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
    page_text=soup.get_text(' ',strip=True)
    dated=re.search(r'Date of Analysis:\s*Data used is as of\s*([A-Za-z]+\s+\d{4})',page_text,re.I)
    observation=dated.group(1) if dated else 'Not published / not parsed'
    # First large-firm panel: rating cell followed immediately by its spread.
    for row in soup.select('tr'):
        cells=[c.get_text(' ',strip=True) for c in row.find_all(['td','th'],recursive=False)]
        for i,c in enumerate(cells[:4]):
            if re.fullmatch(r'Baa2\s*/\s*BBB',c) and i+1<len(cells):
                m=re.fullmatch(r'([\d.]+)\s*%',cells[i+1])
                if m: return float(m.group(1))/100,meta(SPREAD_URL,observation)
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



def standard_corporate_tax(df, iso3):
    """Choose only OECD's combined, statutory, general-government corporate rate.

    Fail closed on ambiguous or missing classifications, rather than use the
    first row from a multi-dimensional OECD dataset.
    """
    required={'REF_AREA','TIME_PERIOD','OBS_VALUE'}
    if not required.issubset(df.columns):
        raise ValueError('OECD CSV is missing REF_AREA/TIME_PERIOD/OBS_VALUE')
    rows=df.loc[df['REF_AREA'].astype(str).str.upper()==iso3.upper()].copy()
    if rows.empty: return None,{}
    dimension_filters=[
        (('TARGETING','TAX_TARGET','TAX_TARG'), 'ST'),
        (('INSTITUTIONAL_SECTOR','SECTOR','INST_SECTOR'), 'S13'),
    ]
    for options,code in dimension_filters:
        column=next((n for n in options if n in rows.columns),None)
        if column is None:
            raise ValueError(f'OECD classification column missing for {code}')
        rows=rows[rows[column].astype(str).str.upper()==code]
    # OECD 2.0: dimension "MEASURE" stores the combined CIT rate as CIT_C.
    # If the measure column is absent, it is unsafe to assume the CSV is combined.
    measure=next((n for n in ('MEASURE','CIT_MEASURE') if n in rows.columns),None)
    if measure is None: raise ValueError('Cannot identify the combined CIT measure')
    rows=rows[rows[measure].astype(str).str.upper()=='CIT_C']
    if rows.empty: return None,{}
    rows['TIME_PERIOD']=pd.to_numeric(rows['TIME_PERIOD'],errors='coerce')
    rows['OBS_VALUE']=pd.to_numeric(rows['OBS_VALUE'],errors='coerce')
    rows=rows.dropna(subset=['TIME_PERIOD','OBS_VALUE'])
    if rows.empty: return None,{}
    year=int(rows['TIME_PERIOD'].max())
    latest=rows[rows['TIME_PERIOD']==year]
    values=latest['OBS_VALUE'].drop_duplicates()
    if len(values)!=1: raise ValueError('Ambiguous combined OECD rates for latest year')
    rate=float(values.iloc[0])
    if not 0 <= rate <= 100: raise ValueError('OECD tax rate outside 0–100%')
    return rate/100, {'year':year,'definition':'Combined statutory corporate rate, general government','source':'OECD CIT SDMX 2.0'}


def bond_detail(slug):
    """Fetch the actual 10-year yield from a country's Trading Economics bond page.

    Reads explicit Actual quote text rather than forecasts or unrelated maturities.
    Refuses to invent a quote if the provider blocks access or changes markup.
    """
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug):
        raise ValueError('Invalid country slug')
    url=f'https://tradingeconomics.com/{slug}/government-bond-yield'
    soup=BeautifulSoup(get(url).text,'html.parser')
    heading=soup.find('h1')
    if heading is None or not re.search(r'10\s*year|10\s*y(?:ear)?',heading.get_text(' ',strip=True),re.I):
        raise ValueError('The quote page is not explicitly labeled as a 10-year bond')
    # Extract the headline actual, never the forecast; HTML text blocks may
    # change with the Trading Economics frontend.
    text=soup.get_text(' ',strip=True)
    head=re.search(r'\bActual\s+(-?\d{1,3}(?:\.\d{1,5})?)\b',text,re.I)
    if head is None:
        raise ValueError('Could not locate the current Actual 10-year quote')
    value=float(head.group(1))
    if not -20 < value < 100:
        raise ValueError('Implausible 10-year yield')
    # Extract explicit observation date if published in the summary.
    dates=re.search(r'last updated on\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2})\s+(?:of\s+)?(20\d{2})',text,re.I)
    if dates:
        observation=f'{dates.group(1)}, {dates.group(2)}'
    else:
        dates=re.search(r'(?:on|updated on)\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2})',text,re.I)
        observation=dates.group(1) if dates else 'Date not parsed; verify on source'
    return value/100, meta(url,observation)

BONDS_COUNTRY_URL='https://tradingeconomics.com/country-list/government-bond-10y'

def parse_country_bond_table(html):
    """Parse the public Trading Economics 10Y country-list table.

    Only accept a table explicitly headed Country / Last / Reference;
    ignore forecasts, unrelated maturities and non-country ad rows.
    """
    soup=BeautifulSoup(html,'html.parser')
    output=[]
    for table in soup.find_all('table'):
        header=[c.get_text(' ',strip=True).lower().replace('▲','').strip()
                for c in table.select('thead th')]
        if not header:
            top=table.find('tr')
            if top is not None:
                header=[c.get_text(' ',strip=True).lower().replace('▲','').strip()
                        for c in top.find_all(['th','td'],recursive=False)]
        def col(part):
            return next((i for i,h in enumerate(header) if h==part or h.startswith(part+' ')),None)
        country_idx,last_idx,ref_idx=col('country'),col('last'),col('reference')
        if country_idx is None or last_idx is None or ref_idx is None:
            continue
        for tr in table.select('tr'):
            cells=tr.find_all(['td','th'],recursive=False)
            if len(cells)<=max(country_idx,last_idx,ref_idx):
                continue
            country=cells[country_idx].get_text(' ',strip=True)
            value=cells[last_idx].get_text(' ',strip=True).replace(',','').replace('%','')
            date=cells[ref_idx].get_text(' ',strip=True)
            if not re.fullmatch(r'-?\\d{1,3}(?:\\.\\d+)?',value):
                continue
            numeric=float(value)
            if not (-20<numeric<100):
                continue
            if not re.fullmatch(r'[A-Za-z][A-Za-z .()\\-]{1,60}',country):
                continue
            if country.lower() in ('report','country list','world'):
                continue
            # Reference is often just month/year; preserve it without inventing a day.
            if not re.fullmatch(r'[A-Za-z]{3}/\\d{2,4}',date):
                continue
            slug=re.sub(r'[^a-z0-9]+','-',country.lower()).strip('-')
            output.append(dict(country=country,slug=slug,yield_rate=numeric/100,
                               observation_date=date,
                               source=BONDS_COUNTRY_URL))
    if not output:
        raise ValueError('No 10-year country yield table with Country/Last/Reference headings was found')
    return pd.DataFrame(output).drop_duplicates('country')


def bonds():
    """Fetch country-level 10Y yields from the public, server-rendered TE country list.

    This is a different page than /bonds, whose table is rendered client-side.
    No API key or preloaded market data are used.
    """
    try:
        html=get(BONDS_COUNTRY_URL).text
        result=parse_country_bond_table(html)
    except Exception as exc:
        raise ValueError(f'Trading Economics country-list fetch failed: {exc}') from exc
    return result,meta(BONDS_COUNTRY_URL,'See observation_date in each country row')
