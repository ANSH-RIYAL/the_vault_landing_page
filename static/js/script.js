// Function to calculate SIP returns
function calculateSIPReturns(monthlyInvestment, annualReturn, years) {
    const monthlyRate = annualReturn / 12 / 100;
    const months = years * 12;
    const totalInvestment = monthlyInvestment * months;
    
    // Future Value of SIP formula
    const futureValue = monthlyInvestment * 
        ((Math.pow(1 + monthlyRate, months) - 1) / monthlyRate) * 
        (1 + monthlyRate);
    
    return {
        totalInvestment: totalInvestment,
        futureValue: futureValue,
        returns: futureValue - totalInvestment
    };
}

// Function to format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(amount);
}

// Function to update SIP projection
function updateSIPProjection(annualReturn) {
    const monthlyInvestment = 50;
    
    // Calculate 1-year returns
    const oneYearResult = calculateSIPReturns(monthlyInvestment, annualReturn, 1);
    
    // Calculate 40-year returns
    const fortyYearResult = calculateSIPReturns(monthlyInvestment, annualReturn, 40);
    
    // Update the display
    document.getElementById('sip-returns').textContent = `${annualReturn.toFixed(2)}%`;
    document.getElementById('sip-returns-40year').textContent = `${annualReturn.toFixed(2)}`;
    document.getElementById('sip-40year-total').textContent = formatCurrency(fortyYearResult.futureValue);
}

// Function to format date to month
function formatDateToMonth(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('default', { month: 'short' });
}

// Function to fetch and display S&P 500 data
async function fetchSP500Data() {
    try {
        const response = await fetch('/sp500-data');
        const data = await response.json();
        
        if (!data.dates || !data.prices || data.dates.length === 0) {
            console.error('No data available');
            return;
        }
        
        // Format dates to show only months
        const monthLabels = data.dates.map(formatDateToMonth);
        
        const ctx = document.getElementById('sp500Chart');
        const loadingElement = document.getElementById('chart-loading');
        
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: monthLabels,
                datasets: [{
                    label: 'S&P 500 Performance',
                    data: data.prices,
                    borderColor: '#57068C',
                    backgroundColor: 'rgba(87, 6, 140, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            callback: function(value, index, values) {
                                // Only show the first occurrence of each month
                                const currentMonth = monthLabels[index];
                                if (index === 0) return currentMonth;
                                const prevMonth = monthLabels[index - 1];
                                return currentMonth === prevMonth ? '' : currentMonth;
                            }
                        }
                    },
                    y: {
                        beginAtZero: false,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    }
                }
            }
        });
        
        // Calculate returns
        const firstPrice = data.prices[0];
        const lastPrice = data.prices[data.prices.length - 1];
        const annualReturn = ((lastPrice - firstPrice) / firstPrice) * 100;
        
        // Update SIP projections
        document.getElementById('sip-returns').textContent = `${annualReturn.toFixed(2)}%`;
        document.getElementById('sip-returns-40year').textContent = annualReturn.toFixed(2);
        
        // Calculate 40-year projection
        const monthlyInvestment = 50;
        const years = 40;
        const monthlyRate = annualReturn / 100 / 12;
        const months = years * 12;
        
        let futureValue = 0;
        for (let i = 0; i < months; i++) {
            futureValue += monthlyInvestment;
            futureValue *= (1 + monthlyRate);
        }
        
        document.getElementById('sip-40year-total').textContent = `$${futureValue.toLocaleString(undefined, {maximumFractionDigits: 0})}`;
        
        // Hide loading indicator
        loadingElement.style.display = 'none';
    } catch (error) {
        console.error('Error fetching data:', error);
        const loadingElement = document.getElementById('chart-loading');
        if (loadingElement) {
            loadingElement.textContent = 'Error loading data';
        }
    }
}

// WebSocket connection for real-time updates
let ws = null;

function connectWebSocket() {
    // Use wss:// for HTTPS and ws:// for HTTP
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/interest`;
    console.log('Connecting to WebSocket:', wsUrl);
    
    ws = new WebSocket(wsUrl);
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        const interestCountElement = document.getElementById('interestCount');
        if (interestCountElement) {
            interestCountElement.textContent = `${data.count} people are interested`;
        }
    };
    
    ws.onclose = function() {
        // Try to reconnect after 5 seconds
        setTimeout(connectWebSocket, 5000);
    };
}

// Function to handle email subscription
async function handleEmailSubscription(event) {
    event.preventDefault();
    const emailInput = event.target.querySelector('#emailInput');
    const messageElement = event.target.parentElement.querySelector('#subscribeMessage');
    const email = emailInput.value.trim();
    
    if (!email) {
        messageElement.textContent = 'Please enter a valid email address';
        messageElement.classList.remove('hidden', 'text-nyu-green');
        messageElement.classList.add('text-red-500');
        return;
    }
    
    try {
        const response = await fetch('/subscribe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email }),
        });
        
        const data = await response.json();
        
        if (response.ok) {
            messageElement.textContent = 'Successfully subscribed!';
            messageElement.classList.remove('hidden', 'text-red-500');
            messageElement.classList.add('text-nyu-green');
            emailInput.value = '';
        } else {
            messageElement.textContent = data.detail || 'Subscription failed';
            messageElement.classList.remove('hidden', 'text-nyu-green');
            messageElement.classList.add('text-red-500');
        }
    } catch (error) {
        messageElement.textContent = 'An error occurred. Please try again.';
        messageElement.classList.remove('hidden', 'text-nyu-green');
        messageElement.classList.add('text-red-500');
    }
}

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    // Connect WebSocket
    connectWebSocket();
    
    // Interest button functionality
    const interestButton = document.getElementById('interestButton');
    const emailSection = document.getElementById('emailSection');
    
    if (interestButton && emailSection) {
        interestButton.addEventListener('click', async () => {
            try {
                const response = await fetch('/increment-interest', { method: 'POST' });
                const data = await response.json();
                
                // Disable button and update its appearance
                interestButton.disabled = true;
                interestButton.classList.add('bg-gray-400');
                interestButton.classList.remove('hover:bg-nyu-violet');
                
                // Show email section
                emailSection.classList.remove('hidden');
            } catch (error) {
                console.error('Error:', error);
            }
        });
    }
    
    // Email subscription form
    const subscribeForm = document.getElementById('subscribeForm');
    if (subscribeForm) {
        subscribeForm.addEventListener('submit', handleEmailSubscription);
    }
    
    // Initial data fetch
    fetchSP500Data();

    // Admin Authentication
    const adminForm = document.getElementById('adminForm');
    const adminLink = document.getElementById('adminLink');
    
    if (adminForm) {
        adminForm.addEventListener('submit', function(e) {
            e.preventDefault();
            handleAdminAuth();
        });
    }
    
    if (adminLink) {
        adminLink.addEventListener('click', function(e) {
            e.preventDefault();
            window.open('/admin', '_blank');
        });
    }
});

// Admin Authentication
function handleAdminAuth() {
    const password = document.getElementById('adminPassword').value;
    console.log('Admin auth attempt with password:', password);
    
    if (password === ADMIN_PASSWORD) {
        console.log('Password correct, opening admin page');
        // Open admin page in new window with password as query parameter
        const adminUrl = `/admin?password=${encodeURIComponent(password)}`;
        console.log('Opening URL:', adminUrl);
        window.open(adminUrl, '_blank');
        // Reset the form
        document.getElementById('adminPassword').value = '';
        document.getElementById('adminForm').classList.add('hidden');
    } else {
        console.log('Invalid password');
        alert('Invalid password');
    }
}

// Admin Stats
async function fetchAdminStats() {
    try {
        const response = await fetch('/admin/stats');
        const data = await response.json();
        
        // Update stats
        document.getElementById('adminTotalInterest').textContent = data.total_interest;
        document.getElementById('adminUniqueVisitors').textContent = data.unique_visitors;
        document.getElementById('adminTotalSubscribers').textContent = data.total_subscribers;
        
        // Update recent interest
        const recentInterestDiv = document.getElementById('adminRecentInterest');
        recentInterestDiv.innerHTML = data.recent_interest.map(item => `
            <div class="admin-recent-item">
                <span class="admin-recent-value">${item[0]}</span>
                <span class="admin-recent-timestamp">${new Date(item[1]).toLocaleString()}</span>
            </div>
        `).join('');
        
        // Update recent subscribers
        const recentSubscribersDiv = document.getElementById('adminRecentSubscribers');
        recentSubscribersDiv.innerHTML = data.recent_subscribers.map(item => `
            <div class="admin-recent-item">
                <span class="admin-recent-value">${item[0]}</span>
                <span class="admin-recent-timestamp">${new Date(item[1]).toLocaleString()}</span>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error fetching admin stats:', error);
    }
}

// Function to download database as CSV
async function downloadDatabaseCSV(password) {
    try {
        const response = await fetch(`/export-data?password=${encodeURIComponent(password)}`);
        if (!response.ok) {
            throw new Error('Failed to fetch data');
        }
        
        const data = await response.json();
        
        // Create CSV content
        let csvContent = "data:text/csv;charset=utf-8,";
        
        // Add summary section
        csvContent += "Summary\n";
        csvContent += "Total Interest,Unique Visitors,Total Subscribers\n";
        csvContent += `${data.summary.total_interest},${data.summary.unique_visitors},${data.summary.total_subscribers}\n\n`;
        
        // Add interest data
        csvContent += "Interest Data\n";
        csvContent += "IP Address,Timestamp\n";
        data.interest_data.forEach(item => {
            // Clean the data: remove any commas and escape quotes
            const cleanIP = item.ip_address.replace(/"/g, '""');
            const cleanTimestamp = item.timestamp.replace(/"/g, '""');
            csvContent += `"${cleanIP}","${cleanTimestamp}"\n`;
        });
        
        // Add email subscribers
        csvContent += "\nEmail Subscribers\n";
        csvContent += "Email,Timestamp\n";
        data.email_data.forEach(item => {
            // Clean the data: remove any commas and escape quotes
            const cleanEmail = item.email.replace(/"/g, '""');
            const cleanTimestamp = item.timestamp.replace(/"/g, '""');
            csvContent += `"${cleanEmail}","${cleanTimestamp}"\n`;
        });
        
        // Create download link
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `database_export_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } catch (error) {
        console.error('Error downloading database:', error);
        alert('Failed to download database. Please check the console for details.');
    }
} 