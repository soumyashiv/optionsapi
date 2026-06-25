document.addEventListener('DOMContentLoaded', () => {
    const themeToggleBtn = document.getElementById('theme-toggle');
    const form = document.getElementById('fetch-form');
    const symbolInput = document.getElementById('symbol');
    const isIndexSelect = document.getElementById('is_index');
    const exchangeSelect = document.getElementById('exchange');
    const submitBtn = document.getElementById('submit-btn');
    
    const loader = document.getElementById('loader');
    const errorMsg = document.getElementById('error-msg');
    const resultsDiv = document.getElementById('results');
    const tbody = document.getElementById('chain-body');
    
    // Theme toggle
    const currentTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', currentTheme);
    themeToggleBtn.textContent = currentTheme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode';

    themeToggleBtn.addEventListener('click', () => {
        let theme = document.documentElement.getAttribute('data-theme');
        let newTheme = theme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        themeToggleBtn.textContent = newTheme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode';
    });

    let autoRefreshInterval = null;
    let isFetching = false;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const symbol = symbolInput.value.trim().toUpperCase();
        const isIndex = isIndexSelect.value;
        const exchange = exchangeSelect.value;
        
        if (!symbol) return;

        // UI Reset (Only on initial manual load)
        errorMsg.style.display = 'none';
        resultsDiv.style.display = 'none';
        loader.style.display = 'block';
        submitBtn.disabled = true;

        await fetchData(symbol, isIndex, exchange, true);

        // Start auto-refresh in the background every 1 minute
        if (autoRefreshInterval) clearInterval(autoRefreshInterval);
        autoRefreshInterval = setInterval(() => {
            fetchData(symbol, isIndex, exchange, false);
        }, 60000); 
    });

    async function fetchData(symbol, isIndex, exchange, isInitialLoad) {
        if (isFetching) return;
        isFetching = true;
        
        try {
            const url = `/api/options?symbol=${symbol}&is_index=${isIndex}&exchange=${exchange}`;
            const response = await fetch(url);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to fetch option chain data');
            }

            renderData(data);
            
            if (isInitialLoad) {
                resultsDiv.style.display = 'block';
            }
            
            errorMsg.style.display = 'none';
            document.getElementById('last-updated').textContent = `Live Data • Last updated: ${new Date().toLocaleTimeString()}`;
            document.getElementById('last-updated').style.color = '#787b86';
            
        } catch (error) {
            console.error("Fetch error:", error);
            if (isInitialLoad) {
                errorMsg.textContent = error.message;
                errorMsg.style.display = 'block';
            } else {
                // For background polling, just update the status text instead of hiding data
                document.getElementById('last-updated').textContent = `Background update failed • Last updated: ${new Date().toLocaleTimeString()} (Retrying soon)`;
                document.getElementById('last-updated').style.color = 'var(--put-color)';
            }
        } finally {
            if (isInitialLoad) {
                loader.style.display = 'none';
                submitBtn.disabled = false;
            }
            isFetching = false;
        }
    }

    function renderData(data) {
        // Render Summary
        document.getElementById('spot-price').textContent = data.spot_price ? data.spot_price.toFixed(2) : 'N/A';
        document.getElementById('atm-strike').textContent = data.atm_strike || 'N/A';
        document.getElementById('expiry-date').textContent = data.expiry || 'N/A';
        document.getElementById('symbol-display').textContent = data.symbol;

        // Render Table
        tbody.innerHTML = '';
        
        if (!data.data || data.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="center">No data available for this symbol.</td></tr>';
            return;
        }

        data.data.forEach(row => {
            const tr = document.createElement('tr');
            
            if (row.strike === data.atm_strike) {
                tr.classList.add('row-atm');
            }

            // Calls
            tr.appendChild(createCell(row.call_oi, 'call-data'));
            tr.appendChild(createCell(row.call_coi, 'call-data text-call', true));
            tr.appendChild(createCell(row.call_iv ? row.call_iv.toFixed(2) : '-', 'call-data'));
            tr.appendChild(createCell(row.call_ltp ? row.call_ltp.toFixed(2) : '-', 'call-data text-call', false, true));
            
            // Strike
            tr.appendChild(createCell(row.strike, 'strike-col'));
            
            // Puts
            tr.appendChild(createCell(row.put_ltp ? row.put_ltp.toFixed(2) : '-', 'put-data text-put', false, true));
            tr.appendChild(createCell(row.put_iv ? row.put_iv.toFixed(2) : '-', 'put-data'));
            tr.appendChild(createCell(row.put_coi, 'put-data text-put', true));
            tr.appendChild(createCell(row.put_oi, 'put-data'));

            tbody.appendChild(tr);
        });
        
        // Scroll ATM strike into view if available
        setTimeout(() => {
            const atmRow = document.querySelector('.row-atm');
            if (atmRow) {
                // Ensure table container scrolls to the right place
                atmRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }, 100);
    }

    function createCell(content, className, isCoi = false, isLtp = false) {
        const td = document.createElement('td');
        if (isCoi && typeof content === 'number') {
            td.textContent = (content > 0 ? '+' : '') + content;
            if (content > 0) td.style.color = 'var(--call-color)';
            else if (content < 0) td.style.color = 'var(--put-color)';
        } else {
            td.textContent = content;
            if (isLtp && content !== '-') {
                td.style.fontWeight = '600';
            }
        }
        if (className) {
            td.className = className;
        }
        return td;
    }
});
