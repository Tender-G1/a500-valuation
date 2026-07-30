// 图表交互逻辑
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
        pe: data.pe.slice(start),
        pb: data.pb.slice(start),
        pe_pct: data.pe_pct.slice(start),
        erp_pct: data.erp_pct.slice(start)
    };
}

function initChart() {
    const ctx = document.getElementById('valuationChart').getContext('2d');
    const data = getWindowData(currentWindow, chartData);
    
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.dates,
            datasets: [
                {
                    label: 'PE (TTM)',
                    data: data.pe,
                    borderColor: '#60a5fa',
                    backgroundColor: 'rgba(96, 165, 250, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                    borderWidth: 2,
                    yAxisID: 'y'
                },
                {
                    label: 'PE分位 (%)',
                    data: data.pe_pct,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.05)',
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    borderWidth: 1.5,
                    borderDash: [4, 4],
                    yAxisID: 'y1'
                },
                {
                    label: 'ERP分位 (%)',
                    data: data.erp_pct,
                    borderColor: '#a78bfa',
                    backgroundColor: 'rgba(167, 139, 250, 0.05)',
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    borderWidth: 1.5,
                    borderDash: [2, 4],
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
                    labels: {
                        color: '#aaa',
                        font: { size: 11 },
                        boxWidth: 14,
                        padding: 12
                    }
                },
                tooltip: {
                    backgroundColor: '#1a1a2e',
                    titleColor: '#e0e0e0',
                    bodyColor: '#ccc',
                    borderColor: '#333366',
                    borderWidth: 1,
                    callbacks: {
                        label: function(ctx) {
                            let label = ctx.dataset.label || '';
                            let val = ctx.parsed.y;
                            if (ctx.dataset.yAxisID === 'y') {
                                return label + ': ' + val.toFixed(2) + 'x';
                            } else {
                                return label + ': ' + val.toFixed(1) + '%';
                            }
                        }
                    }
                },
                annotation: {
                    annotations: {
                        pe20: {
                            type: 'line',
                            yMin: chartData.pe_20,
                            yMax: chartData.pe_20,
                            borderColor: 'rgba(34, 197, 94, 0.4)',
                            borderWidth: 1,
                            borderDash: [6, 4],
                            label: {
                                content: 'PE 20%',
                                enabled: true,
                                position: 'start',
                                backgroundColor: 'rgba(34, 197, 94, 0.2)',
                                color: '#22c55e',
                                font: { size: 9 }
                            }
                        },
                        pe80: {
                            type: 'line',
                            yMin: chartData.pe_80,
                            yMax: chartData.pe_80,
                            borderColor: 'rgba(239, 68, 68, 0.4)',
                            borderWidth: 1,
                            borderDash: [6, 4],
                            label: {
                                content: 'PE 80%',
                                enabled: true,
                                position: 'start',
                                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                                color: '#ef4444',
                                font: { size: 9 }
                            }
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#666', maxTicksLimit: 20 }
                },
                y: {
                    position: 'left',
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#888' },
                    title: { display: true, text: 'PE (x)', color: '#888' }
                },
                y1: {
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#888', callback: function(v) { return v + '%'; } },
                    min: 0,
                    max: 100,
                    title: { display: true, text: '分位 (%)', color: '#888' }
                }
            }
        }
    });
    
    // 标记最新日期
    const meta = chart.getDatasetMeta(0);
    if (meta.data.length > 0) {
        const last = meta.data[meta.data.length - 1];
        // 无法直接添加标注，用额外dataset? 简单起见跳过
    }
}

function updateChart(window) {
    currentWindow = window;
    const data = getWindowData(window, chartData);
    chart.data.labels = data.dates;
    chart.data.datasets[0].data = data.pe;
    chart.data.datasets[1].data = data.pe_pct;
    chart.data.datasets[2].data = data.erp_pct;
    chart.update();
    
    // 更新按钮状态
    document.querySelectorAll('.btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.window === window);
    });
}

// 历史表格
function renderTable() {
    const tbody = document.getElementById('historyTable');
    const len = chartData.dates.length;
    const start = Math.max(0, len - 30);
    let html = '';
    for (let i = len - 1; i >= start; i--) {
        html += `<tr>
            <td>${chartData.dates[i]}</td>
            <td>${chartData.pe[i] ? chartData.pe[i].toFixed(2) : 'N/A'}</td>
            <td>${chartData.pb[i] ? chartData.pb[i].toFixed(2) : 'N/A'}</td>
            <td>${chartData.pe_pct[i] ? chartData.pe_pct[i].toFixed(1) : 'N/A'}%</td>
            <td>${chartData.erp_pct[i] ? chartData.erp_pct[i].toFixed(1) : 'N/A'}%</td>
        </tr>`;
    }
    tbody.innerHTML = html;
}

// 事件绑定
document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('click', function() {
        updateChart(this.dataset.window);
    });
});

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    if (typeof chartData !== 'undefined' && chartData.dates.length > 0) {
        initChart();
        renderTable();
    } else {
        document.querySelector('.chart-container').innerHTML = '<p style="color:#888;text-align:center;padding:40px;">暂无数据，请等待系统更新</p>';
    }
});
