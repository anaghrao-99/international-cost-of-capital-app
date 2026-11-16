import json
from dataclasses import asdict
from datetime import datetime, timezone
import pandas as pd
import pycountry
import streamlit as st
import data
from model import Inputs, calculate

st.set_page_config(page_title='International Cost of Capital',layout='wide')
st.title('International Cost of Capital')
st.caption('USD and target-country currency • explicit assumptions • public-source data')
st.caption('Active manual overrides persist when you change country or refresh. Review them for the selected project.')

@st.cache_data(ttl=3600,show_spinner=False)
def fetch(name):
    try:
        value, metadata=getattr(data,name)()
        return value, metadata, None
    except Exception as exc:
        return None, {}, str(exc)

if st.button('Refresh all source data',help='Clears the one-hour cache and retries every source; overrides remain active.'):
    fetch.clear()
    st.rerun()
source={}
with st.spinner('Retrieving public sources…'):
    for name in ['betas','spread','taxes','bonds']:
        source[name]=fetch(name)

countries={c.name:c.alpha_3 for c in pycountry.countries}
countries['United States']='USA'
names=sorted(countries)
with st.sidebar:
    st.header('Project inputs')
    country=st.selectbox('Target country',names,index=names.index('United States'))
    use_foreign_tax=st.toggle('Use target-country corporate tax rate',value=False,help='Off: use US corporate tax rate for both currency calculations. On: use the target country rate for both.')
    tax_country=country if use_foreign_tax else 'United States'
    st.caption(f'Project tax jurisdiction: {tax_country}')
    erp=st.number_input('USD equity risk premium (%)',0.0,100.0,6.5,0.1)/100
    debt=st.slider('Debt / (debt + equity) (%)',0,99,30)/100

beta_df=source['betas'][0]
industries=sorted(beta_df.industry.astype(str).unique()) if beta_df is not None else ['Software (System & Application)']
default=next((i for i,s in enumerate(industries) if 'software' in s.lower() and 'system' in s.lower()),0)
industry=st.selectbox('US industry',industries,index=default)
beta_value=float(beta_df.set_index('industry').loc[industry,'beta']) if beta_df is not None else None

def input_override(label, live, key, percent=False, maximum=100.0):
    enabled=st.checkbox('Manually override '+label,key=key+'_enabled')
    if enabled:
        v=st.number_input(label+(' (%)' if percent else ''),min_value=-99.0 if 'yield' in key else 0.0,max_value=maximum,
                          value=float(live*100 if percent else live) if live is not None else 0.0,
                          key=key+'_value',format='%.4f')
        note=st.text_input('Source / observation date for '+label,key=key+'_note')
        if not note: st.warning('Add a source/date note for this manual input before submission.')
        return v/100 if percent else v,dict(mode='manual',note=note)
    if live is None:
        st.warning(label+': unavailable. Enable manual override to calculate.')
    else:
        st.caption(f'{label}: {live*100 if percent else live:.4f}'+('%' if percent else '')+' (fetched)')
    return live,dict(mode='fetched')

live_tax=None
tax_note={}
taxdf=source['taxes'][0]
with st.expander('OECD series selection (confirm standard combined statutory rate)',expanded=taxdf is not None):
    upload=st.file_uploader('Optional OECD CSV fallback (original SDMX CSV with REF_AREA, TIME_PERIOD, OBS_VALUE)',type='csv')
    if upload:
        try:
            taxdf=pd.read_csv(upload)
            if not {'REF_AREA','TIME_PERIOD','OBS_VALUE'}.issubset(taxdf): raise ValueError('Missing SDMX columns')
            tax_note={'uploaded_file':upload.name}
        except Exception as e:
            st.error(str(e)); taxdf=None
    if taxdf is not None:
        try:
            subset=data.tax_series(taxdf[taxdf.REF_AREA==countries[tax_country]])
            if subset.empty: st.warning('No OECD observations for this jurisdiction.')
            else:
                series=st.selectbox('OECD series dimensions',sorted(subset['_series'].unique()))
                confirmed=st.checkbox('I confirm this is the standard combined central + subcentral statutory corporate tax rate, in percent (not an SME or targeted rate).')
                selected=subset[subset['_series']==series].copy()
                selected['TIME_PERIOD']=pd.to_numeric(selected.TIME_PERIOD,errors='coerce')
                selected['OBS_VALUE']=pd.to_numeric(selected.OBS_VALUE,errors='coerce')
                selected=selected.dropna(subset=['TIME_PERIOD','OBS_VALUE'])
                latest=selected[selected.TIME_PERIOD==selected.TIME_PERIOD.max()]
                st.dataframe(latest,hide_index=True)
                if confirmed and latest.OBS_VALUE.nunique()==1:
                    rate=float(latest.OBS_VALUE.iloc[0])
                    if 0<=rate<=100:
                        live_tax=rate/100
                        tax_note.update(year=int(latest.TIME_PERIOD.iloc[0]),series=series)
                elif confirmed: st.error('Ambiguous observations; use a manual tax input.')
        except Exception as e: st.error('Cannot interpret OECD CSV: '+str(e))

yields=source['bonds'][0]
def yield_for(name):
    if yields is None: return None,{}
    aliases={'United States':'united-states','United Kingdom':'united-kingdom','Korea, Republic of':'south-korea','Russian Federation':'russia','Türkiye':'turkey'}
    slug=aliases.get(name,name.lower().replace(' ','-'))
    rows=yields[yields.slug==slug]
    return (float(rows.iloc[0].yield_rate),rows.iloc[0].to_dict()) if len(rows)==1 else (None,{})
us,us_meta=yield_for('United States')
foreign,foreign_meta=yield_for(country)
if country=='United States' and foreign is None and us is not None:
    foreign,foreign_meta=us,dict(us_meta,derived='Same US 10-year benchmark; identical currency')
with st.expander('Source values and manual overrides',expanded=True):
    beta,beta_mode=input_override('Unlevered beta',beta_value,'beta',maximum=20.)
    tax,tax_mode=input_override('Corporate tax rate',live_tax,'tax',True)
    spread,spread_mode=input_override('USD BBB spread',source['spread'][0],'spread',True)
    us,us_mode=input_override('US 10-year government yield',us,'us_yield',True)
    if country=='United States':
        foreign=us
        foreign_mode=dict(mode='linked',note='United States selected: target yield equals US yield')
        st.caption(f'Target-country 10-year yield: uses the same US benchmark ({us:.3%})' if us is not None else 'Target-country yield: linked to US yield; enter US yield above.')
    else:
        foreign,foreign_mode=input_override('Target 10-year government yield',foreign,'foreign_yield',True)
    fs_enabled=st.checkbox('Override target-currency BBB spread')
    fs=None
    if fs_enabled:
        fs=st.number_input('Target-currency BBB spread (%)',0.0,100.0,0.0,format='%.4f')/100
        fs_note=st.text_input('Foreign spread source / date')
    else: fs_note='Automatic: USD spread × currency conversion factor'

provenance={name:dict(metadata=m,error=e) for name,(_,m,e) in source.items()}
provenance.update(tax_selection=tax_note,us_yield=us_meta,target_yield=foreign_meta,
                  overrides=dict(beta=beta_mode,tax=tax_mode,spread=spread_mode,us_yield=us_mode,foreign_yield=foreign_mode,foreign_spread=fs_note))
with st.expander('Sources, observation dates, retrieval times and fetch diagnostics'):
    st.json(provenance)
    st.caption('Retrieval time is not an observation date. Missing source dates are explicitly unavailable. Manual overrides take priority. No bundled market observations are used.')

if all(v is not None for v in [beta,tax,spread,us,foreign]):
    x=Inputs(beta,tax,erp,debt,us,foreign,spread,fs)
    try: result=calculate(x)
    except ValueError as e: st.error(str(e)); st.stop()
    st.subheader('Cost of capital results')
    usd_col, target_col = st.columns(2)
    with usd_col:
        st.markdown('#### 🇺🇸 USD')
        st.metric('Cost of equity',f"{result['usd_equity']:.2%}")
        st.metric('Pre-tax cost of debt',f"{result['usd_debt']:.2%}")
        st.metric('WACC',f"{result['usd_wacc']:.2%}")
    with target_col:
        st.markdown(f'#### {country} benchmark currency')
        st.metric('Cost of equity',f"{result['foreign_equity']:.2%}")
        st.metric('Pre-tax cost of debt',f"{result['foreign_debt']:.2%}")
        st.metric('WACC',f"{result['foreign_wacc']:.2%}")
    st.caption(f'Using the {tax_country} project tax rate ({tax:.2%}) for BOTH calculations; ERP {erp:.2%}; debt financing {debt:.0%}.')
    table=pd.DataFrame({'Metric':['Cost of equity','Pre-tax cost of debt','After-tax cost of debt','WACC'],
                        'USD':[result['usd_equity'],result['usd_debt'],result['usd_debt']*(1-tax),result['usd_wacc']],
                        f'{country} currency':[result['foreign_equity'],result['foreign_debt'],result['foreign_debt']*(1-tax),result['foreign_wacc']]})
    st.dataframe(table.style.format({c:'{:.3%}' for c in table.columns[1:]}),hide_index=True,width='stretch')
    st.caption(f"Levered beta {result['levered_beta']:.4f} • Conversion factor {result['conversion_factor']:.6f} • Target BBB spread {result['foreign_spread']:.3%}")
    st.download_button('Export results CSV',table.to_csv(index=False),'results.csv','text/csv')
    audit=dict(created_utc=datetime.now(timezone.utc).isoformat(),industry=industry,country=country,tax_jurisdiction=tax_country,inputs=asdict(x),results=result,provenance=provenance)
    st.download_button('Export inputs, results and sources JSON',json.dumps(audit,indent=2,default=str),'audit.json','application/json')
    if beta_df is not None:
        rows=[]
        for _,r in beta_df.iterrows():
            y=calculate(Inputs(float(r.beta),tax,erp,debt,us,foreign,spread,fs))
            rows.append({'Industry':r.industry,'Unlevered beta':r.beta,'USD WACC':y['usd_wacc'],'Target WACC':y['foreign_wacc']})
        compare=pd.DataFrame(rows).set_index('Industry')
        st.subheader('Industry comparison')
        st.caption('Uses each fetched industry beta, with all other active assumptions held constant. Selected-industry beta override is not applied to this comparison.')
        st.dataframe(compare.style.format({'Unlevered beta':'{:.4f}','USD WACC':'{:.3%}','Target WACC':'{:.3%}'}))
        st.bar_chart(compare[['USD WACC','Target WACC']])
        st.download_button('Export industry comparison',compare.to_csv(),'industries.csv','text/csv')
else:
    missing=[label for label,value in [
        ('Unlevered industry beta',beta),('Corporate tax rate',tax),
        ('USD BBB spread',spread),('US 10-year yield',us),
        (f'{country} 10-year yield',foreign)] if value is None]
    st.error('Results are not available yet because these source inputs are missing: '+', '.join(missing)+'.')
    st.info('Open **Source values and manual overrides** above. For each missing field, tick its manual override, enter a verified rate, and add the source/date. Results then appear automatically. No missing input is silently replaced with zero.')
    with st.expander('Source error details',expanded=False):
        for source_name,(_,metadata,error) in source.items():
            if error: st.write(f'**{source_name}:** {error}')
    st.caption('The Trading Economics public page may omit its live yield table or block automated requests. In that case use the linked website and a dated manual yield; a live quote cannot be verified automatically.')

with st.expander('Methodology and limitations'):
    st.markdown(r'''
All rates use decimals internally; inputs display percentages. Let d = D/(D+E), t = selected tax rate.

- Levered beta = unlevered beta × [1 + (1−t) d/(1−d)]. Assumes debt beta zero.
- USD equity = US 10y yield + levered beta × USD ERP.
- USD debt = US 10y yield + USD BBB spread.
- q = (1 + target 10y yield)/(1 + US 10y yield).
- Target equity = (1 + USD equity) q − 1.
- Automatic target spread = USD spread × q; target debt = target yield + target spread.
- A manual target spread changes target debt and target WACC only.
- WACC in each currency = (1−d) equity + d debt (1−t).

The yield ratio is an assumed nominal currency conversion proxy, **not** a measured inflation differential or exchange-rate forecast. Sovereign yields embed credit/liquidity risks; no separate country risk premium is added. Convert equity and debt before weighting: converting WACC directly would change the tax-shield treatment. Use nominal cash flows in the same currency as the discount rate. Tax jurisdiction is independent of currency. Standard combined statutory tax is a proxy for the marginal tax shield, assumed fully usable. Negative yields are allowed. Debt share cannot equal 100%.

Class formulas were not supplied in the reference. Verify this methodology against your instructor's formulas before submission. A country with no quoted 10-year bond requires a defensible manual proxy and disclosure. A country's bond currency must be verified by the user, especially for dollarized economies and monetary unions.
''')
