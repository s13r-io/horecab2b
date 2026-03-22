/**
 * NAM Procurement Platform - Dashboard Script
 * Inventory and Menu views for CEO transparency
 */

const API_BASE = '';


// ====== Tab Switching ======

document.querySelectorAll('.db-tab').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

function switchTab(tabName) {
    document.querySelectorAll('.db-tab').forEach(b =>
        b.classList.toggle('active', b.dataset.tab === tabName)
    );
    document.getElementById('inventoryView').style.display = tabName === 'inventory' ? 'block' : 'none';
    document.getElementById('menuView').style.display = tabName === 'menu' ? 'block' : 'none';
    document.getElementById('vendorsView').style.display = tabName === 'vendors' ? 'block' : 'none';

    if (tabName === 'inventory') loadInventory();
    if (tabName === 'menu') loadMenu();
    if (tabName === 'vendors') loadVendors();
}


// ====== Inventory ======

let inventoryCache = null;

async function loadInventory(force) {
    if (inventoryCache && !force) { renderInventory(inventoryCache); return; }

    document.getElementById('inventoryContent').innerHTML =
        '<p class="loading-text">Loading inventory...</p>';

    try {
        const res = await fetch(API_BASE + '/api/inventory-dashboard');
        if (!res.ok) throw new Error('Failed to load');
        const data = await res.json();
        inventoryCache = data;
        renderInventory(data);
    } catch (err) {
        document.getElementById('inventoryContent').innerHTML =
            '<p class="loading-text">Error loading inventory data.</p>';
    }
}

function formatCutoffTime(time24) {
    var parts = time24.split(':');
    var h = parseInt(parts[0]);
    var suffix = h >= 12 ? 'PM' : 'AM';
    var h12 = h > 12 ? h - 12 : (h === 0 ? 12 : h);
    return h12 + ':' + parts[1] + ' ' + suffix;
}

function renderInventory(data) {
    document.getElementById('inventoryDate').textContent =
        'As of ' + data.snapshot_date + ', ' + formatCutoffTime(data.current_time);
    var container = document.getElementById('inventoryContent');

    container.innerHTML = data.ingredients.map(function(ing) {
        var daysVal = ing.days_of_stock !== null ? ing.days_of_stock.toFixed(1) : '--';
        var daysClass = ing.days_of_stock !== null ? 'val-' + ing.status : '';

        // Best-case delivery text
        var deliveryText = 'N/A';
        if (ing.vendors && ing.vendors.length > 0) {
            var best = ing.vendors[0]; // sorted: best first
            deliveryText = best.earliest_delivery;
        }

        // Vendor detail rows
        var vendorRows = '';
        if (ing.vendors && ing.vendors.length > 0) {
            vendorRows = ing.vendors.map(function(v) {
                var cutoffDisplay = formatCutoffTime(v.order_cutoff_time);
                var statusClass = v.cutoff_missed ? 'cutoff-missed' : 'cutoff-ok';
                var statusText = v.cutoff_missed ? 'Missed' : 'Order by ' + cutoffDisplay;
                var priceText = v.latest_price !== null ? 'Rs.' + v.latest_price : '--';
                var avgText = v.avg_price !== null ? 'Rs.' + v.avg_price : '--';

                var reliPct = Math.round(v.reliability_score * 100);
                var moqText = v.moq > 0 ? v.moq + ' ' + ing.unit : '--';
                return '<tr>' +
                    '<td>' + esc(v.vendor_name) + ' <span class="vendor-reliability">(' + reliPct + '% reliable)</span></td>' +
                    '<td>' + cutoffDisplay + '</td>' +
                    '<td class="' + statusClass + '">' + statusText + '</td>' +
                    '<td>' + v.earliest_delivery + '</td>' +
                    '<td class="num">' + moqText + '</td>' +
                    '<td class="num">' + priceText + '</td>' +
                    '<td class="num">' + avgText + '</td>' +
                '</tr>';
            }).join('');
        } else {
            vendorRows = '<tr><td colspan="7" class="no-vendors">No vendors available</td></tr>';
        }

        return '<div class="inv-card" onclick="this.classList.toggle(\'expanded\')">' +
            '<div class="inv-row">' +
                '<div class="inv-left">' +
                    '<span class="dot dot-' + ing.status + '"></span>' +
                    '<div class="inv-info">' +
                        '<span class="inv-name">' + esc(ing.name) + '</span>' +
                        '<span class="inv-meta">' + esc(ing.category) + '</span>' +
                    '</div>' +
                '</div>' +
                '<div class="inv-stats">' +
                    '<div class="inv-stat">' +
                        '<span class="inv-stat-value">' + ing.quantity_on_hand + ' ' + ing.unit + '</span>' +
                        '<span class="inv-stat-label">On Hand</span>' +
                    '</div>' +
                    '<div class="inv-stat">' +
                        '<span class="inv-stat-value">' + ing.avg_daily_consumption + ' ' + ing.unit + '</span>' +
                        '<span class="inv-stat-label">Daily Use</span>' +
                    '</div>' +
                    '<div class="inv-stat">' +
                        '<span class="inv-stat-value ' + daysClass + '">' + daysVal + 'd</span>' +
                        '<span class="inv-stat-label">Stock Left</span>' +
                    '</div>' +
                    '<div class="inv-stat">' +
                        '<span class="inv-stat-value">' + deliveryText + '</span>' +
                        '<span class="inv-stat-label">Earliest Delivery</span>' +
                    '</div>' +
                    '<div class="inv-stat">' +
                        '<span class="inv-stat-value ' + (ing.forecast_order > 0 ? 'val-order' : '') + '">' +
                            (ing.forecast_order > 0 ? ing.forecast_order + ' ' + ing.unit : '--') +
                            (ing.moq_applied ? '<br><span class="moq-note">MOQ: ' + ing.moq + ' ' + ing.unit + '</span>' : '') +
                        '</span>' +
                        '<span class="inv-stat-label">Order Qty</span>' +
                    '</div>' +
                    '<span class="expand-icon">&#9660;</span>' +
                '</div>' +
            '</div>' +
            '<div class="inv-details">' +
                '<table class="inv-vendor-table">' +
                    '<thead><tr>' +
                        '<th>Vendor</th>' +
                        '<th>Cutoff</th>' +
                        '<th>Status</th>' +
                        '<th>Earliest Delivery</th>' +
                        '<th class="num">MOQ</th>' +
                        '<th class="num">Latest Price</th>' +
                        '<th class="num">Avg Price</th>' +
                    '</tr></thead>' +
                    '<tbody>' + vendorRows + '</tbody>' +
                '</table>' +
            '</div>' +
        '</div>';
    }).join('');
}


// ====== Menu ======

let menuCache = null;

async function loadMenu(force) {
    if (menuCache && !force) { renderMenu(menuCache); return; }

    document.getElementById('menuContent').innerHTML = '<p class="loading-text">Loading menu data...</p>';

    try {
        const res = await fetch(API_BASE + '/api/menu-dashboard');
        if (!res.ok) throw new Error('Failed to load');
        const data = await res.json();
        menuCache = data;
        renderMenu(data);
    } catch (err) {
        document.getElementById('menuContent').innerHTML =
            '<p class="loading-text">Error loading menu data.</p>';
    }
}

function renderMenu(data) {
    document.getElementById('menuPeriod').textContent =
        'Last 7 days: ' + data.period_start + ' to ' + data.period_end;
    const container = document.getElementById('menuContent');

    container.innerHTML = data.dishes.map(dish => {
        const hasSales = dish.total_sold > 0;

        const ingRows = dish.ingredients.map(ing =>
            '<tr>' +
                '<td>' + esc(ing.name) + '</td>' +
                '<td class="num">' + ing.qty_per_serving + ' ' + ing.unit + '</td>' +
                '<td class="num">' + ing.total_consumed.toFixed(2) + ' ' + ing.unit + '</td>' +
            '</tr>'
        ).join('');

        return '<div class="dish-card" onclick="this.classList.toggle(\'expanded\')">' +
            '<div class="dish-row">' +
                '<div class="dish-info">' +
                    '<span class="dish-name">' + esc(dish.dish_name) + '</span>' +
                    '<span class="dish-meta">' + esc(dish.category) + ' | ' +
                        dish.avg_daily_sold + ' avg/day</span>' +
                '</div>' +
                '<div class="dish-stats">' +
                    '<div class="dish-stat">' +
                        '<span class="dish-stat-value' + (hasSales ? '' : ' zero') + '">' +
                            (hasSales ? dish.total_sold + ' sold' : 'Not sold') + '</span>' +
                        '<span class="dish-stat-label">Last 7 days</span>' +
                    '</div>' +
                    '<span class="expand-icon">&#9660;</span>' +
                '</div>' +
            '</div>' +
            '<div class="dish-ingredients">' +
                '<table class="ing-table">' +
                    '<thead><tr>' +
                        '<th>Ingredient</th>' +
                        '<th class="num">Per Serving</th>' +
                        '<th class="num">Total Used (7d)</th>' +
                    '</tr></thead>' +
                    '<tbody>' + ingRows + '</tbody>' +
                '</table>' +
            '</div>' +
        '</div>';
    }).join('');
}


// ====== Vendors ======

let vendorsCache = null;

async function loadVendors(force) {
    if (vendorsCache && !force) { renderVendors(vendorsCache); return; }

    document.getElementById('vendorsContent').innerHTML =
        '<p class="loading-text">Loading vendor data...</p>';

    try {
        const res = await fetch(API_BASE + '/api/vendors-dashboard');
        if (!res.ok) throw new Error('Failed to load');
        const data = await res.json();
        vendorsCache = data;
        renderVendors(data);
    } catch (err) {
        document.getElementById('vendorsContent').innerHTML =
            '<p class="loading-text">Error loading vendor data.</p>';
    }
}

function renderVendors(data) {
    document.getElementById('vendorsDate').textContent =
        'As of ' + data.snapshot_date + ', ' + formatCutoffTime(data.snapshot_time);
    var container = document.getElementById('vendorsContent');

    container.innerHTML = data.vendors.map(function(v) {
        var reliPct = Math.round(v.reliability_score * 100);
        var qualPct = Math.round(v.quality_score * 100);
        var cutoffDisplay = formatCutoffTime(v.order_cutoff_time);
        var statusClass = v.cutoff_missed ? 'cutoff-missed' : 'cutoff-ok';
        var statusText = v.cutoff_missed ? 'Cutoff missed' : 'Order by ' + cutoffDisplay;

        var ingRows = '';
        if (v.ingredients && v.ingredients.length > 0) {
            ingRows = v.ingredients.map(function(ing) {
                var latestText = ing.latest_price !== null ? 'Rs.' + ing.latest_price : '--';
                var avgText = ing.avg_price !== null ? 'Rs.' + ing.avg_price : '--';
                var moqText = ing.moq > 0 ? ing.moq + ' ' + esc(ing.unit) : '--';
                return '<tr>' +
                    '<td>' + esc(ing.name) + '</td>' +
                    '<td class="num">' + esc(ing.unit) + '</td>' +
                    '<td class="num">' + moqText + '</td>' +
                    '<td class="num">' + latestText + '</td>' +
                    '<td class="num">' + avgText + '</td>' +
                '</tr>';
            }).join('');
        } else {
            ingRows = '<tr><td colspan="5" class="no-vendors">No ingredients listed</td></tr>';
        }

        return '<div class="vendor-card" onclick="this.classList.toggle(\'expanded\')">' +
            '<div class="vendor-row">' +
                '<div class="vendor-left">' +
                    '<div class="vendor-info">' +
                        '<span class="vendor-name">' + esc(v.vendor_name) + '</span>' +
                        '<span class="vendor-meta">' + esc(v.category) + '</span>' +
                    '</div>' +
                '</div>' +
                '<div class="vendor-stats">' +
                    '<div class="vendor-stat">' +
                        '<span class="vendor-stat-value">' + v.ingredient_count + '</span>' +
                        '<span class="vendor-stat-label">Items</span>' +
                    '</div>' +
                    '<div class="vendor-stat">' +
                        '<span class="vendor-stat-value">' + reliPct + '%</span>' +
                        '<span class="vendor-stat-label">Reliability</span>' +
                    '</div>' +
                    '<div class="vendor-stat">' +
                        '<span class="vendor-stat-value">' + qualPct + '%</span>' +
                        '<span class="vendor-stat-label">Quality</span>' +
                    '</div>' +
                    '<div class="vendor-stat">' +
                        '<span class="vendor-stat-value ' + statusClass + '">' + statusText + '</span>' +
                        '<span class="vendor-stat-label">Today\'s Cutoff</span>' +
                    '</div>' +
                    '<div class="vendor-stat">' +
                        '<span class="vendor-stat-value">' + v.effective_lead_days + 'd</span>' +
                        '<span class="vendor-stat-label">Lead Time</span>' +
                    '</div>' +
                    '<div class="vendor-stat">' +
                        '<span class="vendor-stat-value">' + (v.credit_available ? v.credit_days + 'd' : 'No') + '</span>' +
                        '<span class="vendor-stat-label">Credit</span>' +
                    '</div>' +
                    '<span class="expand-icon">&#9660;</span>' +
                '</div>' +
            '</div>' +
            '<div class="vendor-details">' +
                '<div class="vendor-contact-bar">' +
                    '<span>Contact: ' + esc(v.contact) + '</span>' +
                    '<span>WhatsApp: ' + esc(v.whatsapp) + '</span>' +
                    '<span>Delivery: ' + esc(v.delivery_time) + '</span>' +
                    '<span>Language: ' + esc(v.comm_language.toUpperCase()) + '</span>' +
                '</div>' +
                '<table class="vendor-ing-table">' +
                    '<thead><tr>' +
                        '<th>Ingredient</th>' +
                        '<th class="num">Unit</th>' +
                        '<th class="num">MOQ</th>' +
                        '<th class="num">Latest Price</th>' +
                        '<th class="num">Avg Price</th>' +
                    '</tr></thead>' +
                    '<tbody>' + ingRows + '</tbody>' +
                '</table>' +
            '</div>' +
        '</div>';
    }).join('');
}


// ====== Utility ======

function esc(text) {
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}


// ====== Init ======

window.addEventListener('load', () => {
    loadInventory();
});
