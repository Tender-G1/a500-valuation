// ============================================================
// 1. 图表交互逻辑（区域着色版）
// ============================================================
let chart = null;
let currentWindow = '1y';

function getWindowData(window, data) {
    const len = data.dates.length;
    let start = 0;
    switch(window) {
        case '1y': start = Math.max(0, len - 252); break;
        case '3y': start = Math.max(0, len - 756); break;
        case '5y': start = Math.max(0, len - 1260); break;
        case 'all': default: start = 0; break;
    }
    return {
        dates: data.dates.slice(start),
        pe_pct: data.pe_pct.slice(start),
        pe: data.pe.slice(start),
        pb: data.pb.slice(start),
        start_index: start,
        full_len: len
    };
}

// 区域着色插件
const zonePlugin = {
    id: 'zonePlugin',
    beforeDraw: function(chart) {
        const ctx = chart.ctx;
        const chartArea = chart.chartArea;
        if (!chartArea) return;
        const yScale = chart.scales.y1;
        if (!yScale) return;
        const zones = [
            { min: 0, max: 20, color: 'rgba(0, 200, 0, 0.15)' },
            { min: 20, max: 40, color: 'rgba(150, 200, 50, 0.12)' },
            { min: 40, max: 60, color: 'rgba(150, 150, 150, 0.08)' },
            { min: 60, max: 80, color: 'rgba(255, 150, 0, 0.15)' },
            { min: 80, max: 100, color: 'rgba(255, 0, 0, 0.15)' }
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

function initChart() {
    const ctx = document.getElementById('valuationChart').getContext('2d');
    const data = getWindowData(currentWindow, chartData);
    
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.dates,
            datasets: [
                {
                    label: 'PE分位 (%)',
                    data: data.pe_pct,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.08)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                    borderWidth: 2.5,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    labels: { color: '#aaa', font: { size: 12 }, boxWidth: 16, padding: 16 }
                },
                tooltip: {
                    backgroundColor: '#1a1a2e',
                    titleColor: '#e0e0e0',
                    bodyColor: '#ccc',
                    borderColor: '#333366',
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
                            yMin: chartData.pe_20 || 20,
                            yMax: chartData.pe_20 || 20,
                            borderColor: '#00CC00',
                            borderWidth: 3,
                            borderDash: [6, 4],
                            label: {
                                content: '20%分位（低估阈值）',
                                enabled: true,
                                position: 'start',
                                backgroundColor: 'rgba(0, 204, 0, 0.2)',
                                color: '#00CC00',
                                font: { size: 10, weight: 'bold' }
                            }
                        },
                        pe80: {
                            type: 'line',
                            yMin: chartData.pe_80 || 80,
                            yMax: chartData.pe_80 || 80,
                            borderColor: '#FF0000',
                            borderWidth: 3,
                            borderDash: [6, 4],
                            label: {
                                content: '80%分位（高估阈值）',
                                enabled: true,
                                position: 'start',
                                backgroundColor: 'rgba(255, 0, 0, 0.2)',
                                color: '#FF0000',
                                font: { size: 10, weight: 'bold' }
                            }
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#666', maxTicksLimit: 20, font: { size: 11 } }
                },
                y1: {
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#888', callback: function(v) { return v + '%'; }, font: { size: 11 } },
                    min: 0,
                    max: 100,
                    title: { display: true, text: '分位 (%)', color: '#888', font: { size: 12 } }
                }
            }
        },
        plugins: [zonePlugin]
    });
    
    markToday(chart, data);
    updateUI(data);
}

// 标记今日位置（大红五角星）
function markToday(chart, data) {
    const todayIdx = data.pe_pct.length - 1;
    if (todayIdx < 0) return;
    const meta = chart.getDatasetMeta(0);
    if (!meta || !meta.data || meta.data.length === 0) return;
    
    const originalDraw = chart.draw;
    chart.draw = function() {
        originalDraw.apply(this, arguments);
        const ctx = this.ctx;
        const meta = this.getDatasetMeta(0);
        if (!meta || !meta.data) return;
        const lastPoint = meta.data[todayIdx];
        if (lastPoint) {
            ctx.save();
            ctx.fillStyle = '#FF0000';
            ctx.shadowColor = '#FF0000';
            ctx.shadowBlur = 15;
            const x = lastPoint.x;
            const y = lastPoint.y;
            const outerRadius = 12;
            const innerRadius = 5;
            const points = 5;
            let rot = -Math.PI / 2;
            const step = Math.PI / points;
            ctx.beginPath();
            for (let i = 0; i < points * 2; i++) {
                const r = i % 2 === 0 ? outerRadius : innerRadius;
                const px = x + r * Math.cos(rot + i * step);
                const py = y + r * Math.sin(rot + i * step);
                if (i === 0) ctx.moveTo(px, py);
                else ctx.lineTo(px, py);
            }
            ctx.closePath();
            ctx.fill();
            ctx.shadowBlur = 0;
            ctx.strokeStyle = 'white';
            ctx.lineWidth = 1.5;
            ctx.stroke();
            ctx.restore();
            ctx.save();
            ctx.fillStyle = '#FF0000';
            ctx.font = 'bold 11px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('★ 今日', x, y - outerRadius - 8);
            ctx.restore();
        }
    };
}

function updateChart(window) {
    currentWindow = window;
    const data = getWindowData(window, chartData);
    chart.data.labels = data.dates;
    chart.data.datasets[0].data = data.pe_pct;
    chart.update();
    document.querySelectorAll('.btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.window === window);
    });
    updateUI(data);
}

// ============================================================
// 2. UI 更新（指标卡片 + 结论 + 大字标题）
// ============================================================
function updateUI(data) {
    const latestPct = data.pe_pct[data.pe_pct.length - 1] || 50;
    const latestPbPct = chartData.pb_pct ? chartData.pb_pct[chartData.pb_pct.length - 1] : 50;
    const latestErpPct = chartData.erp_pct ? chartData.erp_pct[chartData.erp_pct.length - 1] : 50;
    const delta = latestPct - (chartData.pe_pct[chartData.pe_pct.length - 2] || latestPct);
    
    // PE分位
    document.getElementById('peValue').textContent = latestPct.toFixed(1) + '%';
    document.getElementById('peDelta').textContent = (delta >= 0 ? '+' : '') + delta.toFixed(1) + '%';
    document.getElementById('peDelta').style.color = delta > 0 ? '#ef4444' : '#22c55e';
    document.getElementById('fullPeValue').textContent = (chartData.full_pe_pct || latestPct).toFixed(1) + '%';
    
    // PB分位
    document.getElementById('pbValue').textContent = latestPbPct.toFixed(1) + '%';
    document.getElementById('fullPbValue').textContent = (chartData.full_pb_pct || latestPbPct).toFixed(1) + '%';
    
    // ERP分位
    document.getElementById('erpValue').textContent = latestErpPct.toFixed(1) + '%';
    const erpLabel = latestErpPct > 70 ? '高性价比' : (latestErpPct > 30 ? '适中' : '偏低');
    document.getElementById('erpLabel').textContent = erpLabel;
    
    // 综合状态
    let statusText, statusColor;
    if (latestPct < 20) { statusText = '🟢 低估区'; statusColor = '#22c55e'; }
    else if (latestPct < 40) { statusText = '🟢 偏低区'; statusColor = '#66cc66'; }
    else if (latestPct < 60) { statusText = '⬜ 中性区'; statusColor = '#aaaaaa'; }
    else if (latestPct < 80) { statusText = '🟡 偏高区'; statusColor = '#f59e0b'; }
    else { statusText = '🔴 高估区'; statusColor = '#ef4444'; }
    document.getElementById('statusValue').textContent = statusText;
    document.getElementById('statusValue').style.color = statusColor;
    document.getElementById('statusSub').textContent = '较昨日 ' + (delta >= 0 ? '+' : '') + delta.toFixed(1) + ' 个百分点';
    
    // 更新时间和数据点
    document.getElementById('updateTime').textContent = new Date().toLocaleString('zh-CN');
    document.getElementById('dataPoints').textContent = '数据点: ' + chartData.dates.length + ' 条';
    document.getElementById('baseLabel').textContent = '基准: ' + (chartData.base_label || '近10年');
    
    // 大字结论（图表顶部）
    let conclusionEmoji, conclusionText;
    if (latestPct >= 80) {
        conclusionEmoji = '🔴';
        conclusionText = '高估区（' + latestPct.toFixed(0) + '%），建议减仓';
    } else if (latestPct >= 60) {
        conclusionEmoji = '🟡';
        conclusionText = '偏高区（' + latestPct.toFixed(0) + '%），距高估区还差 ' + (80 - latestPct).toFixed(0) + ' 个百分点';
    } else if (latestPct >= 40) {
        conclusionEmoji = '⬜';
        conclusionText = '中性区（' + latestPct.toFixed(0) + '%），维持现有仓位';
    } else if (latestPct >= 20) {
        conclusionEmoji = '🟢';
        conclusionText = '偏低区（' + latestPct.toFixed(0) + '%），可适度关注';
    } else {
        conclusionEmoji = '🟢';
        conclusionText = '低估区（' + latestPct.toFixed(0) + '%），建议分批布局';
    }
    const conclusionDiv = document.getElementById('chartConclusion');
    if (conclusionDiv) {
        conclusionDiv.textContent = conclusionEmoji + ' ' + conclusionText;
        conclusionDiv.style.background = latestPct >= 80 ? 'rgba(239,68,68,0.2)' :
                                         latestPct >= 60 ? 'rgba(245,158,11,0.2)' :
                                         latestPct >= 40 ? 'rgba(150,150,150,0.1)' :
                                         latestPct >= 20 ? 'rgba(34,197,94,0.2)' :
                                         'rgba(34,197,94,0.3)';
    }
    
    // 今日结论
    const conclusionTextDiv = document.getElementById('conclusionText');
    if (conclusionTextDiv && typeof conclusionText !== 'undefined') {
        conclusionTextDiv.textContent = conclusionText + ' | 基准: ' + (chartData.base_label || '近10年');
    }
    
    // ─── 渲染新增模块 ────────────────────────────────
    renderPortfolio();
    renderFund();
    renderMultiIndex();
}

// ============================================================
// 3. 🆕 持仓追踪（N3）
// ============================================================
function renderPortfolio() {
    const container = document.getElementById('portfolioSummary');
    if (!container) return;
    
    if (typeof portfolioData === 'undefined' || !portfolioData || !portfolioData.holdings || portfolioData.holdings.length === 0) {
        container.innerHTML = `
            <div style="padding:20px;text-align:center;color:#666;font-size:0.9em;">
                📭 暂无持仓数据<br>
                <span style="font-size:0.75em;color:#444;">通过网站界面录入交易记录后自动生成</span>
            </div>
        `;
        return;
    }
    
    const p = portfolioData;
    let html = `
        <div class="portfolio-summary">
            <div class="portfolio-total">
                <span>总成本: ¥${p.total_cost.toFixed(0)}</span>
                <span>市值: ¥${p.total_market_value.toFixed(0)}</span>
                <span style="color:${p.total_profit >= 0 ? '#22c55e' : '#ef4444'}">
                    收益: ${p.total_profit >= 0 ? '+' : ''}¥${p.total_profit.toFixed(0)} (${p.total_return >= 0 ? '+' : ''}${p.total_return.toFixed(2)}%)
                </span>
            </div>
            <div class="portfolio-detail">
                ${p.holdings.map(h => `
                    <div class="holding-item">
                        <span><strong>${h.index_name}</strong></span>
                        <span>成本 ¥${h.cost.toFixed(0)}</span>
                        <span style="color:${h.profit >= 0 ? '#22c55e' : '#ef4444'}">
                            ${h.profit >= 0 ? '+' : ''}${h.profit.toFixed(0)} (${h.return_pct >= 0 ? '+' : ''}${h.return_pct.toFixed(2)}%)
                        </span>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    container.innerHTML = html;
}

// ============================================================
// 4. 🆕 资金管理（N1）
// ============================================================
function renderFund() {
    const container = document.getElementById('fundStatus');
    if (!container) return;
    
    if (typeof fundData === 'undefined' || !fundData) {
        container.innerHTML = `<div style="padding:20px;text-align:center;color:#666;">💵 资金数据加载中...</div>`;
        return;
    }
    
    const f = fundData;
    let html = `
        <div class="fund-summary">
            <div class="fund-total">
                <span>总资金: ¥${f.total.toFixed(0)}</span>
                <span style="color:#a78bfa;">日收益: ¥${f.daily_income.toFixed(2)}</span>
            </div>
            <div class="fund-tiers">
                ${f.tiers.map(t => `
                    <div class="fund-tier">
                        <span>${t.name}</span>
                        <span>¥${t.amount.toFixed(0)} (${t.ratio.toFixed(0)}%)</span>
                        <span style="color:#888;font-size:0.8em;">${t.availability}</span>
                        <span style="color:#a78bfa;font-size:0.8em;">+¥${t.daily_income.toFixed(2)}/日</span>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    container.innerHTML = html;
}

// ============================================================
// 5. 🆕 多指数估值榜（N6）
// ============================================================
function renderMultiIndex() {
    const container = document.getElementById('multiIndexRank');
    if (!container) return;
    
    if (typeof multiIndexData === 'undefined' || !multiIndexData || multiIndexData.length === 0) {
        container.innerHTML = `<div style="padding:20px;text-align:center;color:#666;">📊 暂无其他指数数据</div>`;
        return;
    }
    
    let html = `
        <div class="multi-index-table">
            <div class="multi-header">
                <span>指数</span>
                <span>PE分位</span>
                <span>状态</span>
                <span>建议</span>
            </div>
            ${multiIndexData.map(idx => `
                <div class="multi-row">
                    <span><strong>${idx.name}</strong></span>
                    <span>${idx.pe_pct.toFixed(1)}%</span>
                    <span>${idx.status}</span>
                    <span style="font-size:0.85em;color:#888;">${idx.advice}</span>
                </div>
            `).join('')}
        </div>
    `;
    container.innerHTML = html;
}

// ============================================================
// 6. 按钮事件 + 初始化
// ============================================================
document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('click', function() {
        updateChart(this.dataset.window);
    });
});

document.addEventListener('DOMContentLoaded', function() {
    if (typeof chartData !== 'undefined' && chartData.dates && chartData.dates.length > 0) {
        // 从 data.js 读取数据后初始化
        // 注意：data.js 需要包含 portfolioData, fundData, multiIndexData
        initChart();
        // 如果 data.js 已包含这些数据，render 函数会在 updateUI 中调用
        // 如果没有，则单独调用
        if (typeof portfolioData !== 'undefined') renderPortfolio();
        if (typeof fundData !== 'undefined') renderFund();
        if (typeof multiIndexData !== 'undefined') renderMultiIndex();
    } else {
        document.querySelector('.chart-container').innerHTML = '<p style="color:#888;text-align:center;padding:40px;">暂无数据，请等待系统更新</p>';
    }
});

// 如果 data.js 加载后数据已存在，但页面还未渲染，用这个兜底
setTimeout(function() {
    if (typeof chartData !== 'undefined' && chartData.dates && chartData.dates.length > 0 && !chart) {
        initChart();
    }
}, 1000);
