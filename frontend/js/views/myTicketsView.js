const MyTicketsView = {
    async render() {
        const content = document.getElementById('content');
        
        if (!Auth.isLoggedIn()) {
            content.innerHTML = `
                <div class="card">
                    <h2>Мои билеты</h2>
                    <p>Пожалуйста, <a href="#/login">войдите</a> для просмотра ваших билетов.</p>
                </div>
            `;
            return;
        }

        content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const user = await API.getCurrentUser();
            content.innerHTML = `
                <div class="card">
                    <h2>Мои билеты</h2>
                    <p>Пользователь: <strong>${App.escapeHtml(user.username)}</strong></p>
                    <p>Email: <strong>${App.escapeHtml(user.email)}</strong></p>
                </div>
                <div id="tickets-info" class="card">
                    <p>Информация о ваших билетах будет отображаться здесь.</p>
                    <p>Функционал требует интеграции с журналом бронирований.</p>
                </div>
            `;
        } catch (error) {
            content.innerHTML = `<div class="alert alert-error">Ошибка загрузки: ${error.message}</div>`;
        }
    }
};