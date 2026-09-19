// GA4 Web Dashboard Application Logic

document.addEventListener('DOMContentLoaded', () => {
  loadDashboardData();
});

async function loadDashboardData() {
  try {
    // 캐시 방지를 위해 timestamp 파라미터 추가
    const response = await fetch(`data.json?_t=${Date.now()}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    renderDashboard(data);
  } catch (error) {
    console.error('대시보드 데이터 로드 실패:', error);
    document.getElementById('lastUpdated').textContent = '데이터를 불러올 수 없습니다.';
    document.getElementById('lastUpdated').style.color = '#f43f5e';
  }
}

function renderDashboard(data) {
  // 1. 최종 갱신 시각
  if (data.updated_at) {
    document.getElementById('lastUpdated').textContent = data.updated_at;
  }

  // 2. 핵심 KPI 4종 및 증감률
  const kpi = data.kpi || {};
  const changes = data.changes || {};

  renderKpiCard(
    'Users',
    kpi.users ?? 0,
    changes.users
  );

  renderKpiCard(
    'Sessions',
    kpi.sessions ?? 0,
    changes.sessions
  );

  renderKpiCard(
    'PageViews',
    kpi.page_views ?? 0,
    changes.page_views
  );

  renderKpiCard(
    'KeyEvents',
    kpi.key_events ?? 0,
    changes.key_events
  );

  // 3. 최근 7일 추이 차트
  if (data.trends_7d && Array.isArray(data.trends_7d)) {
    renderTrendChart(data.trends_7d);
  }

  // 4. Top Traffic Sources
  if (data.traffic_sources && Array.isArray(data.traffic_sources)) {
    renderTrafficSources(data.traffic_sources);
  }

  // 5. Top Pages
  if (data.top_pages && Array.isArray(data.top_pages)) {
    renderTopPages(data.top_pages);
  }
}

function renderKpiCard(idSuffix, currentValue, changeData) {
  const valElem = document.getElementById(`val${idSuffix}`);
  const badgeElem = document.getElementById(`badge${idSuffix}`);
  const prevElem = document.getElementById(`prev${idSuffix}`);

  if (valElem) {
    valElem.textContent = Number(currentValue).toLocaleString();
  }

  if (changeData && badgeElem) {
    const rate = changeData.rate ?? 0;
    const rateStr = changeData.rate_str || '- 0.0%';
    const prevVal = changeData.previous ?? 0;

    badgeElem.innerHTML = `<span class="change-text">${rateStr}</span>`;
    badgeElem.className = 'metric-change';

    if (rate > 0) {
      badgeElem.classList.add('up');
    } else if (rate < 0) {
      badgeElem.classList.add('down');
    } else {
      badgeElem.classList.add('neutral');
    }

    if (prevElem) {
      prevElem.textContent = `전일: ${Number(prevVal).toLocaleString()}`;
    }
  }
}

let chartInstance = null;

function renderTrendChart(trends) {
  const ctx = document.getElementById('trendChart').getContext('2d');

  // 날짜 레이블 (MM/DD 형태)
  const labels = trends.map(item => {
    if (item.date && item.date.length >= 10) {
      return item.date.substring(5); // '09-12'
    }
    return item.date;
  });

  const usersData = trends.map(item => item.users || 0);
  const sessionsData = trends.map(item => item.sessions || 0);

  // 그라디언트 배경 생성
  const usersGradient = ctx.createLinearGradient(0, 0, 0, 300);
  usersGradient.addColorStop(0, 'rgba(56, 189, 248, 0.35)');
  usersGradient.addColorStop(1, 'rgba(56, 189, 248, 0.0)');

  const sessionsGradient = ctx.createLinearGradient(0, 0, 0, 300);
  sessionsGradient.addColorStop(0, 'rgba(168, 85, 247, 0.25)');
  sessionsGradient.addColorStop(1, 'rgba(168, 85, 247, 0.0)');

  if (chartInstance) {
    chartInstance.destroy();
  }

  chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Users',
          data: usersData,
          borderColor: '#38bdf8',
          backgroundColor: usersGradient,
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointBackgroundColor: '#38bdf8',
          pointBorderColor: '#0a0e17',
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
        },
        {
          label: 'Sessions',
          data: sessionsData,
          borderColor: '#a855f7',
          backgroundColor: sessionsGradient,
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointBackgroundColor: '#a855f7',
          pointBorderColor: '#0a0e17',
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        legend: {
          display: false // 커스텀 레전드 사용
        },
        tooltip: {
          backgroundColor: 'rgba(17, 24, 39, 0.95)',
          titleColor: '#f9fafb',
          bodyColor: '#e5e7eb',
          borderColor: 'rgba(255, 255, 255, 0.1)',
          borderWidth: 1,
          padding: 12,
          cornerRadius: 8,
          titleFont: {
            family: 'Plus Jakarta Sans',
            weight: '700'
          },
          bodyFont: {
            family: 'JetBrains Mono'
          }
        }
      },
      scales: {
        x: {
          grid: {
            color: 'rgba(255, 255, 255, 0.04)',
            drawBorder: false,
          },
          ticks: {
            color: '#9ca3af',
            font: {
              family: 'Plus Jakarta Sans',
              size: 11
            }
          }
        },
        y: {
          beginAtZero: true,
          grid: {
            color: 'rgba(255, 255, 255, 0.06)',
            drawBorder: false,
          },
          ticks: {
            color: '#9ca3af',
            precision: 0,
            font: {
              family: 'JetBrains Mono',
              size: 11
            }
          }
        }
      }
    }
  });
}

function renderTrafficSources(sources) {
  const tbody = document.getElementById('sourceTableBody');
  if (!tbody) return;

  if (sources.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="loading-td">수집된 트래픽 소스가 없습니다.</td></tr>';
    return;
  }

  tbody.innerHTML = sources.map((item, idx) => {
    const rankClass = idx < 3 ? `rank-${idx + 1}` : '';
    return `
      <tr>
        <td><span class="rank-badge ${rankClass}">${idx + 1}</span></td>
        <td><span class="item-path" title="${escapeHtml(item.source)}">${escapeHtml(item.source)}</span></td>
        <td style="text-align: right;"><span class="num-val">${Number(item.sessions).toLocaleString()}</span></td>
        <td style="text-align: right;"><span class="num-val">${Number(item.users).toLocaleString()}</span></td>
      </tr>
    `;
  }).join('');
}

function renderTopPages(pages) {
  const tbody = document.getElementById('pagesTableBody');
  if (!tbody) return;

  if (pages.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="loading-td">수집된 페이지 데이터가 없습니다.</td></tr>';
    return;
  }

  tbody.innerHTML = pages.map((item, idx) => {
    const rankClass = idx < 3 ? `rank-${idx + 1}` : '';
    return `
      <tr>
        <td><span class="rank-badge ${rankClass}">${idx + 1}</span></td>
        <td><span class="item-path" title="${escapeHtml(item.path)}">${escapeHtml(item.path)}</span></td>
        <td style="text-align: right;"><span class="num-val">${Number(item.views).toLocaleString()}</span></td>
        <td style="text-align: right;"><span class="num-val">${Number(item.users).toLocaleString()}</span></td>
      </tr>
    `;
  }).join('');
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
