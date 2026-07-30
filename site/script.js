// 交互图表逻辑（区域着色版）
let chart = null;
let currentWindow = '1y';

// 获取窗口数据
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

// 自定义插件：区域着色（绘制PE分位背景色块）
const zonePlugin = {
    id: 'zonePlugin',
    beforeDraw: function(chart) {
        const ctx = chart.ctx;
        const chartArea = chart.chartArea;
        if (!chartArea) return;
        
        const yScale = chart.scales.y1;
        if (!yScale) return;
        
        // 定义区域：0-20%, 20-40%, 40-60%, 60-80%, 80-100%
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

// 初始化图表
function initChart() {
    const ctx = document.getElementById('valuationChart').getContext('2d');
    const data = getWindowData(currentWindow, chartData);
    
    // 判断是否显示阈值线（基于当前窗口是否有足够的PE数据）
    const hasThresholds = data.pe.length > 0 && chartData.pe_20 && chartData.pe_80;
    
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.dates,
            datasets: [
                // 主曲线：PE分位
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
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#aaa',
                        font: { size: 12 },
                        boxWidth: 16,
                        padding: 16
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
                            return 'PE分位: ' + ctx.parsed.y.toFixed(1) + '%';
                        }
                    }
                },
                // 阈值线（使用annotation插件）
                annotation: {
                    annotations: {
                        pe20: {
                            type: 'line',
                            yMin: chartData.pe_20,
                            yMax: chartData.pe_20,
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
                            yMin: chartData.pe_80,
                            yMax: chartData.pe_80,
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
                    ticks: { 
                        color: '#888', 
                        callback: function(v) { return v + '%'; },
                        font: { size: 11 }
                    },
                    min: 0,
                    max: 100,
                    title: {
                        display: true,
                        text: '分位 (%)',
                        color: '#888',
                        font: { size: 12 }
                    }
                }
            }
        },
        plugins: [zonePlugin]
    });
    
    // ─── M1：标记今日位置（使用额外绘图） ──────────────
    markToday(chart, data);
    
    // 更新今日结论
    updateConclusion(data);
}

// M1：标记今日位置（大红五角星）
function markToday(chart, data) {
    const todayIdx = data.pe_pct.length - 1;
    if (todayIdx < 0) return;
    
    const meta = chart.getDatasetMeta(0);
    if (!meta || !meta.data || meta.data.length === 0) return;
    
    // 在chart绘制完成后叠加五角星
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
            // 绘制五角星
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
            // 添加白色外发光
            ctx.strokeStyle = 'white';
            ctx.lineWidth = 1.5;
            ctx.stroke();
            ctx.restore();
            // 添加"今日"文字标注
            ctx.save();
            ctx.fillStyle = '#FF0000';
            ctx.font = 'bold 11px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('★ 今日', x, y - outerRadius - 8);
            ctx.restore();
        }
    };
}

// 更新结论显示
function updateConclusion(data) {
    const conclusionDiv = document.getElementById('conclusionText');
    if (conclusionDiv && typeof conclusionText !== 'undefined') {
        conclusionDiv.textContent = conclusionText + ' | 基准: ' + (baseLabel || '近10年');
    }
}

// 切换窗口
function updateChart(window) {
    currentWindow = window;
    const data = getWindowData(window, chartData);
    
    // 更新数据
    chart.data.labels = data.dates;
    chart.data.datasets[0].data = data.pe_pct;
    
    // 更新阈值线（基于当前窗口数据重新计算阈值）
    const windowPEPct = data.pe_pct;
    if (windowPEPct.length > 0) {
        const sorted = [...windowPEPct].sort((a, b) => a - b);
        const pe20 = sorted[Math.floor(0.2 * sorted.length)];
        const pe80 = sorted[Math.floor(0.8 * sorted.length)];
        // 更新annotation（通过重新创建）
        chart.options.plugins.annotation.annotations.pe20.yMin = pe20;
        chart.options.plugins.annotation.annotations.pe20.yMax = pe20;
        chart.options.plugins.annotation.annotations.pe80.yMin = pe80;
        chart.options.plugins.annotation.annotations.pe80.yMax = pe80;
    }
    
    chart.update();
    
    // 更新按钮状态
    document.querySelectorAll('.btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.window === window);
    });
}

// DOM就绪
document.addEventListener('DOMContentLoaded', function() {
    if (typeof chartData !== 'undefined' && chartData.dates && chartData.dates.length > 0) {
        // 显示结论
        const conclusionDiv = document.getElementById('conclusionText');
        if (conclusionDiv) {
            conclusionDiv.textContent = (typeof conclusionText !== 'undefined' ? conclusionText : '数据加载中') + ' | 基准: ' + (typeof baseLabel !== 'undefined' ? baseLabel : '近10年');
        }
        initChart();
    } else {
        document.querySelector('.chart-container').innerHTML = '<p style="color:#888;text-align:center;padding:40px;">暂无数据，请等待系统更新</p>';
    }
});

// 按钮事件
document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('click', function() {
        updateChart(this.dataset.window);
    });
});
