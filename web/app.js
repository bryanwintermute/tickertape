document.addEventListener('DOMContentLoaded', () => {
    // --- Theme Settings ---
    const settingsBtn = document.getElementById('settings-btn');
    const settingsMenu = document.getElementById('settings-menu');
    const themeToggle = document.getElementById('theme-toggle');

    // Toggle menu
    settingsBtn.addEventListener('click', (e) => {
        settingsMenu.classList.toggle('show');
        e.stopPropagation();
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!settingsMenu.contains(e.target) && e.target !== settingsBtn) {
            settingsMenu.classList.remove('show');
        }
    });

    // Theme toggle logic
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        themeToggle.checked = false;
    }

    themeToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            document.documentElement.removeAttribute('data-theme');
            localStorage.setItem('theme', 'dark');
        } else {
            document.documentElement.setAttribute('data-theme', 'light');
            localStorage.setItem('theme', 'light');
        }
    });

    // --- Pre-fill from URL params (Web Share Target / Shortcuts) ---
    const urlParams = new URLSearchParams(window.location.search);
    const shareText = urlParams.get('text');
    const shareTitle = urlParams.get('title');
    const shareUrl = urlParams.get('url');
    
    let prefillDone = false;
    if (shareText || shareTitle || shareUrl) {
        let combined = [];
        if (shareTitle) combined.push(`# ${shareTitle}`);
        if (shareText) combined.push(shareText);
        if (shareUrl) combined.push(shareUrl);
        
        const echoInput = document.getElementById('echo-text');
        if (echoInput) {
            echoInput.value = combined.join('\n\n');
            prefillDone = true;
        }
        
        // Clean up URL without reloading
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // --- Tab Switching ---
    const tabs = document.querySelectorAll('.tab-btn');
    const panels = document.querySelectorAll('.panel');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));

            tab.classList.add('active');
            const panelId = `${tab.dataset.tab}-panel`;
            document.getElementById(panelId).classList.add('active');

            if (tab.dataset.tab === 'inbox') {
                loadInbox();
            } else if (tab.dataset.tab === 'history') {
                loadHistory();
            }
        });
    });

    if (prefillDone) {
        const markdownTab = document.querySelector('[data-tab="echo"]');
        if (markdownTab) markdownTab.click();
    }

    // --- Toast Notification ---
    function showToast(message, isError = false) {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        
        if (isError) {
            toast.classList.add('error');
        } else {
            toast.classList.remove('error');
        }

        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    // --- API Helper ---
    function generateUUID() {
        if (window.crypto && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        // Fallback for non-secure contexts (e.g., HTTP IP address access)
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    async function submitJob(payload) {
        try {
            // Generate idempotency key
            payload.idempotency_key = generateUUID();
            
            const response = await fetch('/api/print', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to queue job');
            }

            showToast('Sent to printer queue!');
            return true;
        } catch (err) {
            console.error(err);
            showToast(err.message, true);
            return false;
        }
    }

    // --- Forms ---
    // Echo
    document.getElementById('echo-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const btn = e.target.querySelector('button[type="submit"]');
        const ogText = btn.textContent;
        btn.textContent = 'Sending...';
        btn.disabled = true;

        const payload = {
            type: 'echo',
            title: document.getElementById('echo-title').value,
            text: document.getElementById('echo-text').value,
            save_to_history: document.getElementById('echo-save').checked
        };

        const success = await submitJob(payload);
        if (success) {
            e.target.reset();
        }
        
        btn.textContent = ogText;
        btn.disabled = false;
    });

    document.getElementById('echo-inbox-btn').addEventListener('click', async (e) => {
        const btn = e.target;
        const ogText = btn.textContent;
        btn.textContent = 'Saving...';
        btn.disabled = true;

        const payload = {
            type: 'echo',
            title: document.getElementById('echo-title').value,
            text: document.getElementById('echo-text').value,
            send_to_inbox: true
        };

        const success = await submitJob(payload);
        if (success) {
            document.getElementById('echo-form').reset();
            showToast('Saved to Inbox!');
        }
        
        btn.textContent = ogText;
        btn.disabled = false;
    });

    // List
    document.getElementById('list-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('button');
        const ogText = btn.textContent;
        btn.textContent = 'Sending...';
        btn.disabled = true;

        const itemsRaw = document.getElementById('list-items').value;
        const items = itemsRaw.split('\n').map(i => i.trim()).filter(i => i.length > 0);
        
        const payload = {
            type: 'list', // or 'reminder', depending on semantics. 'list' is immediate for now.
            title: document.getElementById('list-title').value,
            style: document.querySelector('input[name="list-style"]:checked').value,
            items: items,
            save_to_history: document.getElementById('list-save').checked
        };

        const success = await submitJob(payload);
        if (success) {
            e.target.reset();
        }
        
        btn.textContent = ogText;
        btn.disabled = false;
    });

    document.getElementById('list-inbox-btn').addEventListener('click', async (e) => {
        const btn = e.target;
        const ogText = btn.textContent;
        btn.textContent = 'Saving...';
        btn.disabled = true;

        const rawItems = document.getElementById('list-items').value.split('\n');
        const items = rawItems.map(i => i.trim()).filter(i => i.length > 0);

        const payload = {
            type: 'list',
            title: document.getElementById('list-title').value,
            style: document.querySelector('input[name="list-style"]:checked').value,
            items: items,
            send_to_inbox: true
        };

        const success = await submitJob(payload);
        if (success) {
            document.getElementById('list-form').reset();
            showToast('Saved to Inbox!');
        }
        
        btn.textContent = ogText;
        btn.disabled = false;
    });

    // --- Templates ---
    const templates = {
        'shopping': {
            title: 'Shopping List',
            style: 'checkbox',
            items: 'Milk\nEggs\nBread\nCoffee'
        },
        'morning': {
            title: 'Morning Routine',
            style: 'checkbox',
            items: 'Make bed\nDrink water\nStretch\nRead 10 mins'
        }
    };
    
    document.getElementById('list-template-select')?.addEventListener('change', (e) => {
        const val = e.target.value;
        if (templates[val]) {
            document.getElementById('list-title').value = templates[val].title;
            document.getElementById('list-items').value = templates[val].items;
            document.querySelector(`input[name="list-style"][value="${templates[val].style}"]`).checked = true;
        }
        e.target.value = ''; // Reset select
    });

    // --- Inbox Logic ---
    async function loadInbox() {
        const inboxList = document.getElementById('inbox-list');
        inboxList.innerHTML = '<p class="empty-state">Loading...</p>';
        
        try {
            const response = await fetch('/api/inbox');
            if (!response.ok) throw new Error('Failed to load inbox');
            
            const data = await response.json();
            
            if (data.reminders.length === 0) {
                inboxList.innerHTML = '<p class="empty-state">No pending reminders.</p>';
                return;
            }
            
            inboxList.innerHTML = '';
            data.reminders.forEach(reminder => {
                const div = document.createElement('div');
                div.className = 'inbox-item';
                
                div.style.display = 'flex';
                div.style.justifyContent = 'space-between';
                div.style.alignItems = 'center';
                
                const title = reminder.payload.title || 'Untitled Reminder';
                const date = new Date(reminder.created_at).toLocaleString();
                
                const infoDiv = document.createElement('div');
                infoDiv.innerHTML = `
                    <div class="inbox-item-title">${title} (${reminder.status})</div>
                    <div class="inbox-item-meta">Added: ${date}</div>
                `;
                
                const btnDiv = document.createElement('div');
                const printBtn = document.createElement('button');
                printBtn.textContent = 'Print Now';
                printBtn.className = 'primary-btn';
                printBtn.style.padding = '8px 16px';
                printBtn.style.fontSize = '0.9rem';
                printBtn.style.marginTop = '0';
                printBtn.onclick = async () => {
                    const ogText = printBtn.textContent;
                    printBtn.textContent = '...';
                    printBtn.disabled = true;
                    try {
                        const res = await fetch('/api/release_reminder', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ id: reminder.id })
                        });
                        if (res.ok) {
                            loadInbox();
                        } else {
                            throw new Error("Failed");
                        }
                    } catch (e) {
                        console.error(e);
                        printBtn.textContent = 'Error';
                    }
                };
                
                btnDiv.appendChild(printBtn);
                div.appendChild(infoDiv);
                div.appendChild(btnDiv);
                inboxList.appendChild(div);
            });
            
        } catch (err) {
            console.error(err);
            inboxList.innerHTML = '<p class="empty-state" style="color: var(--error-color)">Failed to load inbox.</p>';
        }
    }

    document.getElementById('refresh-inbox').addEventListener('click', loadInbox);
    
    // --- History Logic ---
    async function loadHistory() {
        const historyList = document.getElementById('history-list');
        historyList.innerHTML = '<p class="empty-state">Loading...</p>';
        
        try {
            const response = await fetch('/api/history');
            if (!response.ok) throw new Error('Failed to load history');
            
            const data = await response.json();
            
            if (data.history.length === 0) {
                historyList.innerHTML = '<p class="empty-state">No print history.</p>';
                return;
            }
            
            historyList.innerHTML = '';
            data.history.forEach(job => {
                const div = document.createElement('div');
                div.className = 'inbox-item';
                div.style.display = 'flex';
                div.style.justifyContent = 'space-between';
                div.style.alignItems = 'center';
                
                const title = job.payload.title || (job.type === 'echo' ? 'Quick Note' : 'Untitled List');
                const date = new Date(job.created_at).toLocaleString();
                const statusTag = job.status !== 'printed' ? `<span style="color:var(--error-color);font-size:0.8em">(${job.status})</span>` : '';
                
                const infoDiv = document.createElement('div');
                infoDiv.innerHTML = `
                    <div class="inbox-item-title">${title} <span style="font-weight:normal; font-size: 0.8em; opacity: 0.7;">(${job.type})</span> ${statusTag}</div>
                    <div class="inbox-item-meta">${date}</div>
                `;
                
                const btnDiv = document.createElement('div');
                const reprintBtn = document.createElement('button');
                reprintBtn.textContent = 'Reprint';
                reprintBtn.className = 'primary-btn';
                reprintBtn.style.padding = '8px 16px';
                reprintBtn.style.fontSize = '0.9rem';
                reprintBtn.style.marginTop = '0';
                reprintBtn.onclick = async () => {
                    const ogText = reprintBtn.textContent;
                    reprintBtn.textContent = '...';
                    reprintBtn.disabled = true;
                    // Retain save_to_history as true on reprint so it bumps back to top
                    job.payload.save_to_history = true;
                    await submitJob(job.payload);
                    reprintBtn.textContent = ogText;
                    reprintBtn.disabled = false;
                    loadHistory();
                };
                
                btnDiv.appendChild(reprintBtn);
                div.appendChild(infoDiv);
                div.appendChild(btnDiv);
                historyList.appendChild(div);
            });
            
        } catch (err) {
            console.error(err);
            historyList.innerHTML = '<p class="empty-state" style="color: var(--error-color)">Failed to load history.</p>';
        }
    }

    document.getElementById('refresh-history').addEventListener('click', loadHistory);
});
