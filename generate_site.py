# ─── 在 generate_site.py 的 js_content 部分增加 ──────

# 注入多指数数据
multi_results = scan_all_indices(config, bond_yield)
js_content += f"\nconst multiIndexData = {json.dumps(multi_results, ensure_ascii=False, default=str)};"

# 注入资金数据
fund_status = get_fund_status(config['fund'])
js_content += f"\nconst fundData = {json.dumps(fund_status, ensure_ascii=False, default=str)};"

# 注入持仓数据（解密后）
portfolio_key = os.environ.get("PORTFOLIO_KEY")
if portfolio_key:
    df_portfolio = load_portfolio(portfolio_key)
    current_prices = {'000510': float(today['pe_ttm'])}
    # 可从多指数结果中补充价格
    for r in multi_results:
        if r.get('pe'):
            current_prices[r['code']] = float(r['pe'])
    portfolio_summary = calc_portfolio_summary(df_portfolio, current_prices)
    js_content += f"\nconst portfolioData = {json.dumps(portfolio_summary, ensure_ascii=False, default=str)};"
else:
    js_content += "\nconst portfolioData = null;"

# 注入最新数据（含delta）
js_content += f"""
const latestData = {{
    date: {json.dumps(today['date'].strftime('%Y-%m-%d'), ensure_ascii=False)},
    pe_pct: {pe_pct},
    erp_pct: {erp_pct},
    delta: {delta}
}};
const baseLabel = {json.dumps(base_label, ensure_ascii=False)};
"""
