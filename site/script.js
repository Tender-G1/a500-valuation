const API_BASE = 'https://a500-valuation.vercel.app';
// ============================================================
// 全局变量
// ============================================================
let chart = null;
let currentWindow = '1y';
let chartData = null;
let latestData = null;
let fullData = null;

// ============================================================
// 工具：获取窗口数据 + 动态阈值
// ============================================================
function getWindowData(window, data) {
    const len = data.dates.length;
    let start = 0;
    switch(window) {
        case '1y': start = Math.max(0, len - 252); break;
        case '3y': start = Math.max(0, len - 756); break;
        case '5y': start = Math.max(0, len - 1260); break;
        case 'all': default: start = 0; break;
    }
    const sliced = {
        dates: data.dates.slice(start),
        pe_pct: data.pe_pct.slice(start),
        pe: data.pe.slice(start),
        pb: data.pb.slice(start),
        start_index: start,
        full_len: len
    };
    // 计算当前窗口的阈值（动态）
    const sorted = [...sliced.pe_pct].filter(v => v !== null && v !== undefined).sort((a, b) => a - b);
    if (sorted.length > 0) {
        sliced.pe_20 = sorted[Math.floor(0.2 * sorted.length)];
        sliced.pe_80 = sorted[Math.floor(0.8 * sorted.length)];
    } else {
        sliced.pe_20 = 20;
        sliced.pe_80 = 80;
    }
    return sliced;
}

// ============================================================
// 区域着色插件（颜色更明显）
// ============================================================
const zonePlugin = {
    id: 'zonePlugin',
    beforeDraw: function(chart) {
        const ctx = chart.ctx;
        const chartArea = chart.chartArea;
        if (!chartArea) return;
        const yScale = chart.scales.y1;
        if (!yScale) return;
        const zones = [
            { min: 0, max: 20, color: 'rgba(46, 160, 67, 0.20)' },
            { min: 20, max: 40, color: 'rgba(163, 210, 80, 0.15)' },
            { min: 40, max: 60, color: 'rgba(139, 148, 158, 0.10)' },
            { min: 60, max: 80, color: 'rgba(255, 166, 45, 0.18)' },
            { min: 80, max: 100, color: 'rgba(248, 81, 73, 0.20)' }
        ];
        zones.forEach(zone => {
            const yMin = yScale.getPixelForValue(zone.min);
            const yMax = yScale.getPixelForValue(zone.max);
            const yTop = Math.min(yMin, yMax);
            const yBottom = Math.max(yMin, yMax);
            ctx.save();
            ctx.fillStyle = zone.color;
            ctx.fillRect(chartArea.left, yTop, chartArea.right - chartArea.left, yBottom - yTop);
            ctx.restore();
        });
    }
};

// ============================================================
// 初始化图表
// ============================================================
function initChart() {
    const ctx = document.getElementById('valuationChart').getContext('2d');
    const data = getWindowData(currentWindow, chartData);

    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.dates,
            datasets: [{
                label: 'PE分位 (%)',
                data: data.pe_pct,
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.06)',
                fill: true,
                tension: 0.3,
                pointRadius: 0,
                borderWidth: 2.5,
                yAxisID: 'y1'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    labels: { color: '#8b949e', font: { size: 12 }, boxWidth: 14, padding: 12 }
                },
                tooltip: {
                    backgroundColor: '#161b22',
                    titleColor: '#e6edf3',
                    bodyColor: '#c9d1d9',
                    borderColor: '#30363d',
                    borderWidth: 1,
                    callbacks: {
                        label: function(ctx) {
                            return 'PE分位: ' + ctx.parsed.y.toFixed(1) + '%';
                        }
                    }
                },
                annotation: {
                    annotations: {
                        pe20: {
                            type: 'line',
                            yMin: data.pe_20,
                            yMax: data.pe_20,
                            borderColor: '#3fb950',
                            borderWidth: 3,
                            borderDash: [6, 4],
                            label: {
                                content: '20% 低估阈值',
                                enabled: true,
                                position: 'start',
                                backgroundColor: 'rgba(63, 185, 80, 0.15)',
                                color: '#3fb950',
                                font: { size: 10, weight: 'bold' }
                            }
                        },
                        pe80: {
                            type: 'line',
                            yMin: data.pe_80,
                            yMax: data.pe_80,
                            borderColor: '#f85149',
                            borderWidth: 3,
                            borderDash: [6, 4],
                            label: {
                                content: '80% 高估阈值',
                                enabled: true,
                                position: 'start',
                                backgroundColor: 'rgba(248, 81, 73, 0.15)',
                                color: '#f85149',
                                font: { size: 10, weight: 'bold' }
                            }
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: { color: '#8b949e', maxTicksLimit: 20, font: { size: 10 } }
                },
                y1: {
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: {
                        color: '#8b949e',
                        callback: function(v) { return v + '%'; },
                        font: { size: 10 }
                    },
                    min: 0,
                    max: 100,
                    title: {
                        display: true,
                        text: '分位 (%)',
                        color: '#8b949e',
                        font: { size: 11 }
                    }
                }
            }
        },
        plugins: [zonePlugin]
    });

    // 标记今日位置（五角星）
    markToday(chart, data);
    // 更新结论
    updateConclusion(data);
}

// ============================================================
// 标记今日（修正位置）
// ============================================================
function markToday(chart, data) {
    const todayIdx = data.pe_pct.length - 1;
    if (todayIdx < 0) return;

    // 等待图表渲染完成后绘制
    const originalDraw = chart.draw;
    chart.draw = function() {
        originalDraw.apply(this, arguments);
        const meta = this.getDatasetMeta(0);
        if (!meta || !meta.data || meta.data.length === 0) return;
        const lastPoint = meta.data[todayIdx];
        if (!lastPoint) return;
        const ctx = this.ctx;
        const x = lastPoint.x;
        const y = lastPoint.y;

        ctx.save();
        // 外发光
        ctx.shadowColor = 'rgba(255, 255, 255, 0.3)';
        ctx.shadowBlur = 20;
        // 红色五角星
        ctx.fillStyle = '#f85149';
        const outerR = 14, innerR = 6, points = 5;
        let rot = -Math.PI / 2;
        const step = Math.PI / points;
        ctx.beginPath();
        for (let i = 0; i < points * 2; i++) {
            const r = i % 2 === 0 ? outerR : innerR;
            const px = x + r * Math.cos(rot + i * step);
            const py = y + r * Math.sin(rot + i * step);
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.fill();
        ctx.shadowBlur = 0;
        // 白色描边
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        // 文字标注
        ctx.fillStyle = '#f85149';
        ctx.font = 'bold 12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('★ 今日', x, y - outerR - 10);
        ctx.restore();
    };
}

// ============================================================
// 更新结论
// ============================================================
function updateConclusion(data) {
    const div = document.getElementById('chartConclusion');
    if (!div || !latestData) return;
    const pe = latestData.pe_pct || 0;
    let status = '';
    if (pe >= 80) status = '🔴 高估区';
    else if (pe >= 60) status = '🟡 偏高区（距高估 ' + (80 - pe).toFixed(0) + '%）';
    else if (pe >= 40) status = '⬜ 中性区';
    else if (pe >= 20) status = '🟢 偏低区';
    else status = '🟢 低估区';
    div.innerHTML = '📌 当前PE分位: <strong>' + pe.toFixed(1) + '%</strong> ｜ ' + status;
}

// ============================================================
// 切换窗口（动态更新阈值）
// ============================================================
function updateChart(window) {
    currentWindow = window;
    const data = getWindowData(window, chartData);

    chart.data.labels = data.dates;
    chart.data.datasets[0].data = data.pe_pct;

    // 更新阈值线
    chart.options.plugins.annotation.annotations.pe20.yMin = data.pe_20;
    chart.options.plugins.annotation.annotations.pe20.yMax = data.pe_20;
    chart.options.plugins.annotation.annotations.pe80.yMin = data.pe_80;
    chart.options.plugins.annotation.annotations.pe80.yMax = data.pe_80;

    chart.update();

    // 重新标记今日（位置可能变化）
    setTimeout(() => {
        markToday(chart, data);
        chart.update();
    }, 50);

    // 更新按钮状态
    document.querySelectorAll('.btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.window === window);
    });
}

// ============================================================
// 渲染多指数榜
// ============================================================
function renderMultiIndex(data) {
    const container = document.getElementById('multiIndexRank');
    if (!data || data.length === 0) {
        container.innerHTML = '<div class="loading">暂无其他指数数据</div>';
        return;
    }
    let html = '';
    data.forEach(item => {
        const pct = item.pe_pct || 0;
        let color = '#3fb950';
        if (pct >= 80) color = '#f85149';
        else if (pct >= 60) color = '#f0883e';
        else if (pct >= 40) color = '#8b949e';
        else if (pct >= 20) color = '#3fb950';
        html += `
            <div class="multi-item">
                <div class="name">${item.name}</div>
                <div class="pct" style="color:${color}">${pct.toFixed(1)}%</div>
                <div class="desc">${item.description || ''}</div>
                <div class="advice">${item.advice || ''}</div>
            </div>
        `;
    });
    container.innerHTML = html;
}

// ============================================================
// 渲染资金管理
// ============================================================
function renderFund(data) {
    const container = document.getElementById('fundStatus');
    if (!data || !data.tiers || data.tiers.length === 0) {
        container.innerHTML = '<div class="loading">请配置 config.yaml 中的 fund 参数</div>';
        return;
    }
    let html = `<div class="fund-item" style="grid-column:1/-1;background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:12px 16px;">
        <div class="name">💰 总资金: ¥${(data.total || 0).toLocaleString()}</div>
        <div class="yield">日收益估算: ¥${(data.daily_income || 0).toFixed(2)}</div>
    </div>`;
    data.tiers.forEach(t => {
        html += `
            <div class="fund-item">
                <div class="name">${t.name}</div>
                <div class="amount">¥${(t.amount || 0).toLocaleString()}</div>
                <div class="yield">${t.annual_yield || 0}% ｜ 日收益 ¥${(t.daily_income || 0).toFixed(2)}</div>
                <div class="avail">可用: ${t.availability || 'T+0'}</div>
            </div>
        `;
    });
    container.innerHTML = html;
}

// ============================================================
// 渲染持仓
// ============================================================
function renderPortfolio(data) {
    const container = document.getElementById('portfolioSummary');
    if (!data || !data.holdings || data.holdings.length === 0) {
        container.innerHTML = '<div class="loading">暂无持仓数据，请录入交易记录</div>';
        return;
    }
    let html = `<div class="portfolio-item" style="grid-column:1/-1;background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:12px 16px;">
        <div class="name">📊 总成本: ¥${(data.total_cost || 0).toLocaleString()} ｜ 市值: ¥${(data.total_market_value || 0).toLocaleString()}</div>
        <div class="profit ${(data.total_profit || 0) >= 0 ? 'positive' : 'negative'}">
            收益: ${(data.total_profit || 0) >= 0 ? '+' : ''}¥${(data.total_profit || 0).toLocaleString()} ｜ ${(data.total_return || 0).toFixed(2)}%
        </div>
    </div>`;
    data.holdings.forEach(h => {
        const profit = h.profit || 0;
        html += `
            <div class="portfolio-item">
                <div class="name">${h.index_name || h.index_code}</div>
                <div class="profit ${profit >= 0 ? 'positive' : 'negative'}">
                    ${profit >= 0 ? '+' : ''}${profit.toFixed(0)} (${(h.return_pct || 0).toFixed(2)}%)
                </div>
                <div class="sub">成本 ¥${(h.cost || 0).toLocaleString()} ｜ 市值 ¥${(h.market_value || 0).toLocaleString()}</div>
            </div>
        `;
    });
    container.innerHTML = html;
}

// ============================================================
// 策略提示
// ============================================================
function renderStrategy(pePct, latest) {
    const valueEl = document.getElementById('strategyValue');
    const subEl = document.getElementById('strategySub');
    if (!valueEl || !subEl) return;
    if (!latest || latest.pe_pct === undefined) {
        valueEl.textContent = '--';
        subEl.textContent = '--';
        return;
    }
    const pct = latest.pe_pct || 0;
    let text = '';
    let sub = '';
    if (pct >= 80) {
        text = '🔴 高估区，建议减仓';
        sub = '距离下一卖出区间已触发';
    } else if (pct >= 60) {
        text = '🟡 偏高区，谨慎追高';
        sub = '距高估区还差 ' + (80 - pct).toFixed(1) + '%';
    } else if (pct >= 40) {
        text = '⬜ 中性区，维持仓位';
        sub = '距偏高区 ' + (60 - pct).toFixed(1) + '%';
    } else if (pct >= 20) {
        text = '🟢 偏低区，可关注';
        sub = '距中性区 ' + (40 - pct).toFixed(1) + '%';
    } else {
        text = '🟢 低估区，分批布局';
        sub = '距偏低区 ' + (20 - pct).toFixed(1) + '%';
    }
    valueEl.textContent = text;
    subEl.textContent = sub;
}

// ============================================================
// DOM 就绪
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    if (typeof chartData === 'undefined' || !chartData || !chartData.dates || chartData.dates.length === 0) {
        document.querySelector('.chart-container').innerHTML = '<p style="color:#8b949e;text-align:center;padding:40px;">暂无数据，请等待系统更新</p>';
        return;
    }

    // 更新元信息
    document.getElementById('updateTime').textContent = latestData ? latestData.date + ' 更新' : '--';
    document.getElementById('baseLabel').textContent = '基准: ' + (baseLabel || '近10年');
    document.getElementById('dataPoints').textContent = '数据点: ' + chartData.dates.length + ' 条';

    // 卡片数据
    const pe = latestData ? latestData.pe_pct : 0;
    const erp = latestData ? latestData.erp_pct : 0;
    document.getElementById('peValue').textContent = pe.toFixed(1) + '%';
    document.getElementById('peDelta').textContent = '较昨日 ' + (latestData && latestData.delta !== undefined ? (latestData.delta >= 0 ? '+' : '') + latestData.delta.toFixed(1) + '%' : '--');
    document.getElementById('erpValue').textContent = erp.toFixed(1) + '%';
    document.getElementById('erpLabel').textContent = '性价比 ' + (erp >= 70 ? '高' : erp >= 30 ? '中' : '低');
    let statusText = '';
    if (pe >= 80) statusText = '🔴 高估';
    else if (pe >= 60) statusText = '🟡 偏高';
    else if (pe >= 40) statusText = '⬜ 中性';
    else if (pe >= 20) statusText = '🟢 偏低';
    else statusText = '🟢 低估';
    document.getElementById('statusValue').textContent = statusText;
    document.getElementById('statusSub').textContent = 'PE分位 ' + pe.toFixed(1) + '%';

    // 策略
    renderStrategy(pe, latestData);

    // 初始化图表
    initChart();

    // 渲染各模块
    if (typeof multiIndexData !== 'undefined' && multiIndexData) {
        renderMultiIndex(multiIndexData);
    } else {
        document.getElementById('multiIndexRank').innerHTML = '<div class="loading">暂无其他指数数据</div>';
    }

    if (typeof fundData !== 'undefined' && fundData) {
        renderFund(fundData);
    } else {
        document.getElementById('fundStatus').innerHTML = '<div class="loading">请配置 config.yaml 中的 fund 参数</div>';
    }

    if (typeof portfolioData !== 'undefined' && portfolioData) {
        renderPortfolio(portfolioData);
    } else {
        document.getElementById('portfolioSummary').innerHTML = '<div class="loading">暂无持仓数据，请录入交易记录</div>';
    }

    // ─── 交易表单提交 ──────────────────────────────────
    const form = document.getElementById('transactionForm');
    const resultSpan = document.getElementById('txnResult');
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            const data = {
                index_code: document.getElementById('txnIndex').value,
                index_name: document.getElementById('txnIndex').selectedOptions[0].text,
                action: document.getElementById('txnAction').value,
                amount: parseFloat(document.getElementById('txnAmount').value),
                price: parseFloat(document.getElementById('txnPrice').value) || 0
            };
            if (!data.amount || data.amount <= 0) {
                resultSpan.textContent = '❌ 请输入有效金额';
                resultSpan.style.color = '#f85149';
                return;
            }
            resultSpan.textContent = '⏳ 保存中...';
            try {
                const resp = await fetch('/api/transaction', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await resp.json();
                if (result.success) {
                    resultSpan.textContent = '✅ 保存成功！页面将刷新';
                    resultSpan.style.color = '#3fb950';
                    setTimeout(() => location.reload(), 1500);
                } else {
                    resultSpan.textContent = '❌ ' + (result.error || '保存失败');
                    resultSpan.style.color = '#f85149';
                }
            } catch (err) {
                resultSpan.textContent = '❌ 网络错误，请重试';
                resultSpan.style.color = '#f85149';
            }
        });
    }
});

// ============================================================
// 按钮事件
// ============================================================
document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('click', function() {
        updateChart(this.dataset.window);
    });
});
