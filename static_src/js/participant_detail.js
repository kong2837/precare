(() => {
    const root = document.getElementById('participantDetail');
    if (!root) return;
    const config = JSON.parse(document.getElementById('participant-chart-config').textContent);
    const states = new Map();
    let historyRequest = null;
    const node = (tag, text, className) => {
        const element = document.createElement(tag);
        if (text != null) element.textContent = String(text);
        if (className) element.className = className;
        return element;
    };

    async function showHistory(chart, period, trigger) {
        const panel = document.getElementById('detailSection');
        const area = document.getElementById('modalHistoryArea');
        document.getElementById('detailMetric').textContent = chart.title;
        document.getElementById('detailTitle').textContent = period.label;
        area.replaceChildren(node('p', '상세 기록을 불러오는 중…', 'text-muted small'));
        bootstrap.Offcanvas.getOrCreateInstance(panel).show(trigger);
        if (historyRequest) historyRequest.abort();
        const controller = new AbortController();
        historyRequest = controller;
        const params = new URLSearchParams({metric: chart.metric, start: period.start, end: period.end});
        try {
            const response = await fetch(`${root.dataset.historyUrl}?${params}`, {signal: controller.signal});
            if (!response.ok) throw new Error('history failed');
            const data = await response.json();
            if (controller !== historyRequest) return;
            area.replaceChildren();
            if (!data.history?.length) area.append(node('p', '이 기간에 저장된 기록이 없습니다.', 'text-muted small'));
            for (const item of data.history || []) {
                const article = node('article', null, 'participant-history-item');
                const heading = node('div', null, 'd-flex justify-content-between align-items-center gap-2 mb-2');
                heading.append(node('h3', item.created_at, 'mb-0'), node('span', item.score == null ? '미채점' : `${item.score}점`, 'badge bg-light text-dark border'));
                article.append(heading, node('p', item.title, 'small text-muted mb-2'));
                if (item.has_feedback) {
                    article.append(node('span', item.performed ? '행동 요령 수행 완료' : '행동 요령 미수행', `badge ${item.performed ? 'bg-success' : 'bg-secondary'} mb-2`));
                    article.append(node('p', item.action_msg, 'small mb-0'));
                }
                if (item.answers?.length) {
                    const details = node('details');
                    details.append(node('summary', `문항별 응답 ${item.answers.length}개`));
                    const list = node('ol', null, 'list-unstyled mb-0');
                    for (const answer of item.answers) {
                        const li = node('li');
                        li.append(node('div', `${answer.order}. ${answer.question}`, 'fw-semibold'));
                        li.append(node('div', answer.content || '응답 없음', 'text-muted mt-1'));
                        if (answer.score != null) li.append(node('span', `${answer.score}점`, 'small'));
                        list.append(li);
                    }
                    details.append(list);
                    article.append(details);
                }
                area.append(article);
            }
        } catch (error) {
            if (error.name === 'AbortError') return;
            area.replaceChildren(node('p', '기록을 불러오지 못했습니다. 다시 선택해주세요.', 'text-danger small'));
        }
    }

    function syncGlobalButtons() {
        document.querySelectorAll('[data-all-range]').forEach(button => {
            const active = Array.from(states.values()).every(state => state.range === button.dataset.allRange);
            button.classList.toggle('active', active);
            button.setAttribute('aria-pressed', String(active));
        });
    }

    async function loadChart(chart, range) {
        const state = states.get(chart.metric);
        if (state.controller) state.controller.abort();
        const controller = new AbortController();
        state.controller = controller;
        state.range = range;
        state.card.querySelectorAll('[data-range]').forEach(button => {
            const active = button.dataset.range === range;
            button.classList.toggle('active', active);
            button.setAttribute('aria-pressed', String(active));
        });
        syncGlobalButtons();
        if (state.chart) { state.chart.destroy(); state.chart = null; }
        const status = document.getElementById(`${chart.metric}Empty`);
        const weekly = document.getElementById(`${chart.metric}Weekly`);
        const monthly = document.getElementById(`${chart.metric}Monthly`);
        weekly.classList.add('d-none');
        monthly.classList.add('d-none');
        status.classList.remove('d-none');
        status.replaceChildren(node('span', '불러오는 중…'));
        try {
            const params = new URLSearchParams({metric: chart.metric, range});
            const response = await fetch(`${root.dataset.chartUrl}?${params}`, {signal: controller.signal});
            if (!response.ok) throw new Error('chart failed');
            const data = await response.json();
            if (controller !== state.controller) return;
            if (!data.values?.some(value => typeof value === 'number' && Number.isFinite(value))) {
                status.replaceChildren(node('span', '아직 저장된 설문 점수가 없습니다.'));
                return;
            }
            const canvas = range === 'weekly' ? weekly : monthly;
            const periods = (range === 'weekly' ? data.meta : data.periods) || [];
            status.classList.add('d-none');
            canvas.classList.remove('d-none');
            state.chart = new Chart(canvas, {
                type: 'line',
                data: {labels: data.labels, datasets: [{label: chart.title, data: data.values,
                    borderColor: chart.color, backgroundColor: chart.color, borderWidth: 2,
                    pointRadius: 4, pointHoverRadius: 6, tension: .2, spanGaps: true}]},
                options: {
                    responsive: true, maintainAspectRatio: false,
                    interaction: {mode: 'nearest', intersect: true},
                    plugins: {legend: {display: false}, tooltip: {callbacks: {label: context => `${context.parsed.y}점`}}},
                    scales: {y: {beginAtZero: true, max: data.scale_max || 40, ticks: {stepSize: 5}},
                        x: {ticks: {maxTicksLimit: 4, maxRotation: 0, autoSkip: true}, grid: {display: false}}},
                    onClick: (_, elements) => {
                        if (!elements.length) return;
                        const index = elements[0].index;
                        if (periods[index]) showHistory(chart, {...periods[index], label: data.labels[index]}, canvas);
                    },
                    onHover: (event, elements) => { if (event.native?.target) event.native.target.style.cursor = elements.length ? 'pointer' : 'default'; }
                }
            });
        } catch (error) {
            if (error.name === 'AbortError') return;
            if (controller !== state.controller) return;
            weekly.classList.add('d-none');
            monthly.classList.add('d-none');
            status.classList.remove('d-none');
            const retry = node('button', '다시 불러오기', 'btn btn-outline-secondary btn-sm');
            retry.type = 'button';
            retry.addEventListener('click', () => loadChart(chart, range));
            status.replaceChildren(node('span', '그래프를 불러오지 못했습니다.'), retry);
        }
    }

    config.forEach(chart => {
        const card = root.querySelector(`[data-metric="${chart.metric}"]`);
        states.set(chart.metric, {card, range: 'weekly'});
        card.querySelectorAll('[data-range]').forEach(button => button.addEventListener('click', () => loadChart(chart, button.dataset.range)));
    });
    document.querySelectorAll('[data-all-range]').forEach(button => button.addEventListener('click', () => {
        config.forEach(chart => loadChart(chart, button.dataset.allRange));
    }));
    document.getElementById('detailSection').addEventListener('hidden.bs.offcanvas', () => {
        if (historyRequest) historyRequest.abort();
    });
    config.forEach(chart => loadChart(chart, 'weekly'));
})();
