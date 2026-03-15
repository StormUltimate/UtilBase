// Путь: V:\UtilBase\app\static\js\main.js

let lastScanTime = 0;
const SCAN_COOLDOWN = 5 * 60 * 1000; // 5 минут в миллисекундах

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    const hamburger = document.getElementById('hamburger');
    sidebar.classList.toggle('hidden');
    mainContent.classList.toggle('expanded');
    hamburger.classList.toggle('hidden');
}

async function scanChannels() {
    const now = Date.now();
    if (now - lastScanTime < SCAN_COOLDOWN) {
        showError(`Сканирование доступно раз в 5 минут. Подождите ${Math.ceil((SCAN_COOLDOWN - (now - lastScanTime)) / 1000)} секунд.`);
        return;
    }

    const button = document.getElementById('scanChannelsBtn');
    const spinner = button.querySelector('.spinner');
    spinner.classList.remove('hidden');
    button.disabled = true;

    try {
        const response = await fetch(`/telegram-bot/scan-channels`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.status === 'success') {
            updateChannelList(data.channels);
            lastScanTime = now;
            alert(data.message);
        } else {
            showError(data.message);
        }
    } catch (error) {
        showError(`Ошибка при сканировании каналов: ${error}`);
    } finally {
        spinner.classList.add('hidden');
        button.disabled = false;
    }
}

async function enableChannel(channelId) {
    const button = document.querySelector(`button[onclick="enableChannel('${channelId}')"]`);
    const spinner = button.querySelector('.spinner');
    spinner.classList.remove('hidden');
    button.disabled = true;
    appendToConsole('info', `Включение скачивания для чата ${channelId}...`);
    try {
        const response = await fetch(`/telegram-bot/toggle-download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `action=start&chat_id=${channelId}`
        });
        const data = await response.json();
        appendToConsole('info', `Ответ сервера: ${data.message}`);
        if (data.status === 'success') {
            document.getElementById(`downloadStatus-${channelId}`).textContent = 'Включено';
            button.classList.add('opacity-50', 'cursor-not-allowed');
            button.disabled = true;
            const disableButton = document.querySelector(`button[onclick="disableChannel('${channelId}')"]`);
            disableButton.classList.remove('opacity-50', 'cursor-not-allowed');
            disableButton.disabled = false;
        } else {
            appendToConsole('error', data.message);
            showError(data.message);
        }
    } catch (error) {
        appendToConsole('error', 'Ошибка при включении скачивания: ' + error.message);
        showError('Ошибка при включении скачивания: ' + error.message);
    } finally {
        spinner.classList.add('hidden');
        button.disabled = false;
    }
}

async function disableChannel(channelId) {
    const button = document.querySelector(`button[onclick="disableChannel('${channelId}')"]`);
    const spinner = button.querySelector('.spinner');
    spinner.classList.remove('hidden');
    button.disabled = true;
    appendToConsole('info', `Отключение скачивания для чата ${channelId}...`);
    try {
        const response = await fetch(`/telegram-bot/toggle-download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `action=stop&chat_id=${channelId}`
        });
        const data = await response.json();
        appendToConsole('info', `Ответ сервера: ${data.message}`);
        if (data.status === 'success') {
            document.getElementById(`downloadStatus-${channelId}`).textContent = 'Отключено';
            button.classList.add('opacity-50', 'cursor-not-allowed');
            button.disabled = true;
            const enableButton = document.querySelector(`button[onclick="enableChannel('${channelId}')"]`);
            enableButton.classList.remove('opacity-50', 'cursor-not-allowed');
            enableButton.disabled = false;
        } else {
            appendToConsole('error', data.message);
            showError(data.message);
        }
    } catch (error) {
        appendToConsole('error', 'Ошибка при отключении скачивания: ' + error.message);
        showError('Ошибка при отключении скачивания: ' + error.message);
    } finally {
        spinner.classList.add('hidden');
        button.disabled = false;
    }
}

async function toggleFavorite(channelId, action) {
    const button = document.getElementById(`favoriteBtn-${channelId}`);
    const spinner = button.querySelector('.spinner');
    spinner.classList.remove('hidden');
    button.disabled = true;
    appendToConsole('info', `${action === 'add' ? 'Добавление' : 'Удаление'} чата ${channelId} в избранное...`);
    try {
        const response = await fetch(`/telegram-bot/toggle-favorite`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `action=${action}&chat_id=${channelId}`
        });
        const data = await response.json();
        appendToConsole('info', `Ответ сервера: ${data.message}`);
        if (data.status === 'success') {
            document.getElementById(`favoriteStatus-${channelId}`).textContent = data.is_favorite ? 'Да' : 'Нет';
            button.textContent = data.is_favorite ? 'Удалить из избранного' : 'Добавить в избранное';
            button.setAttribute('onclick', `toggleFavorite('${channelId}', '${data.is_favorite ? "remove" : "add"}')`);
            const channelDiv = document.querySelector(`#channelList .telegram-channel-item:has(#favoriteStatus-${channelId})`);
            if (data.is_favorite) {
                channelDiv.classList.add('favorite');
                // Обновляем статус скачивания
                document.getElementById(`downloadStatus-${channelId}`).textContent = 'Включено';
                document.querySelector(`button[onclick="enableChannel('${channelId}')"]`).classList.add('opacity-50', 'cursor-not-allowed');
                document.querySelector(`button[onclick="enableChannel('${channelId}')"]`).disabled = true;
                document.querySelector(`button[onclick="disableChannel('${channelId}')"]`).classList.remove('opacity-50', 'cursor-not-allowed');
                document.querySelector(`button[onclick="disableChannel('${channelId}')"]`).disabled = false;
            } else {
                channelDiv.classList.remove('favorite');
            }
        } else {
            appendToConsole('error', data.message);
            showError(data.message);
        }
    } catch (error) {
        appendToConsole('error', 'Ошибка при управлении избранным: ' + error.message);
        showError('Ошибка при управлении избранным: ' + error.message);
    } finally {
        spinner.classList.add('hidden');
        button.disabled = false;
    }
}

function updateChannelList(channels) {
    const channelList = document.getElementById('channelList');
    channelList.innerHTML = '';
    if (channels.length === 0) {
        channelList.innerHTML = '<p class="telegram-channel-empty">Каналы не найдены. Нажмите "Сканировать каналы".</p>';
        return;
    }
    channels.forEach(channel => {
        const channelDiv = document.createElement('div');
        channelDiv.className = `telegram-channel-item ${channel.is_favorite ? 'favorite' : ''}`;
        channelDiv.innerHTML = `
            <div class="telegram-channel-details">
                <p class="telegram-channel-info">ID: ${channel.chat_id} | Название: ${channel.title}</p>
                <p class="telegram-channel-info">Скачивание: <span id="downloadStatus-${channel.chat_id}" class="telegram-channel-status">${channel.download_enabled ? 'Включено' : 'Отключено'}</span></p>
                <p class="telegram-channel-info">Избранное: <span id="favoriteStatus-${channel.chat_id}">${channel.is_favorite ? 'Да' : 'Нет'}</span></p>
            </div>
            <div class="telegram-channel-actions">
                <button onclick="toggleFavorite('${channel.chat_id}', '${channel.is_favorite ? "remove" : "add"}')"
                        class="telegram-button telegram-button-purple flex items-center"
                        id="favoriteBtn-${channel.chat_id}">
                    <span class="spinner hidden mr-2 animate-spin h-4 w-4 border-2 border-white rounded-full border-t-transparent"></span>
                    ${channel.is_favorite ? 'Удалить из избранного' : 'Добавить в избранное'}
                </button>
                <button onclick="enableChannel('${channel.chat_id}')"
                        class="telegram-button telegram-button-green flex items-center ${channel.download_enabled ? 'opacity-50 cursor-not-allowed' : ''}"
                        ${channel.download_enabled ? 'disabled' : ''}>
                    <span class="spinner hidden mr-2 animate-spin h-4 w-4 border-2 border-white rounded-full border-t-transparent"></span>
                    Включить
                </button>
                <button onclick="disableChannel('${channel.chat_id}')"
                        class="telegram-button telegram-button-red flex items-center ${!channel.download_enabled ? 'opacity-50 cursor-not-allowed' : ''}"
                        ${!channel.download_enabled ? 'disabled' : ''}>
                    <span class="spinner hidden mr-2 animate-spin h-4 w-4 border-2 border-white rounded-full border-t-transparent"></span>
                    Отключить
                </button>
            </div>
        `;
        channelList.appendChild(channelDiv);
    });
}

function showError(message) {
    const modal = document.getElementById('errorModal');
    const errorMessage = document.getElementById('errorMessage');
    errorMessage.textContent = message;
    modal.classList.remove('hidden');
}

function closeModal() {
    const modal = document.getElementById('errorModal');
    modal.classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
    const hamburger = document.getElementById('hamburger');
    if (hamburger) {
        hamburger.addEventListener('click', toggleSidebar);
    }
});