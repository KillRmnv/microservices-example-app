const AdminView = {
    async renderUsers() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <h2>Управление пользователями</h2>
            <div class="search-bar">
                <input type="text" id="search-email" placeholder="Email...">
                <input type="text" id="search-username" placeholder="Имя пользователя...">
                <select id="search-role">
                    <option value="">Все роли</option>
                    <option value="ADMIN">ADMIN</option>
                    <option value="EVENT_MANAGER">EVENT_MANAGER</option>
                    <option value="CUSTOMER">CUSTOMER</option>
                </select>
                <button class="btn btn-primary" id="search-btn">Найти</button>
            </div>
            <div id="users-container"></div>
        `;

        document.getElementById('search-btn').addEventListener('click', () => this.loadUsers());
        await this.loadUsers();
    },

    async loadUsers() {
        const container = document.getElementById('users-container');
        container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const filter = {
                email: document.getElementById('search-email')?.value || null,
                username: document.getElementById('search-username')?.value || null,
                role: document.getElementById('search-role')?.value || null
            };
            const users = await API.searchUsers(filter);
            this.renderUsersTable(users);
        } catch (error) {
            container.innerHTML = `<div class="alert alert-error">Ошибка: ${error.message}</div>`;
        }
    },

    renderUsersTable(users) {
        const container = document.getElementById('users-container');
        
        if (!users || users.length === 0) {
            container.innerHTML = '<div class="card"><p>Пользователи не найдены</p></div>';
            return;
        }

        container.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Имя</th>
                        <th>Email</th>
                        <th>Роль</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    ${users.map(u => `
                        <tr>
                            <td>${u.id}</td>
                            <td>${App.escapeHtml(u.username)}</td>
                            <td>${App.escapeHtml(u.email)}</td>
                            <td><span class="badge badge-${u.userRole?.name?.toLowerCase() || 'customer'}">${u.userRole?.name || '-'}</span></td>
                            <td class="actions">
                                <button class="btn btn-secondary btn-sm" onclick="AdminView.showEditUserModal(${u.id}, '${App.escapeHtml(u.username)}', '${u.userRole?.name}')">Ред.</button>
                                <button class="btn btn-danger btn-sm" onclick="AdminView.deleteUser(${u.id})">Удалить</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    showEditUserModal(id, username, currentRole) {
        App.showModal(`
            <h2 class="card-title">Редактирование пользователя</h2>
            <form id="edit-user-form">
                <div class="form-group">
                    <label>ID</label>
                    <input type="text" value="${id}" disabled>
                </div>
                <div class="form-group">
                    <label>Имя</label>
                    <input type="text" id="edit-username" value="${App.escapeHtml(username)}">
                </div>
                <div class="form-group">
                    <label>Роль</label>
                    <select id="edit-role">
                        <option value="CUSTOMER" ${currentRole === 'CUSTOMER' ? 'selected' : ''}>CUSTOMER</option>
                        <option value="EVENT_MANAGER" ${currentRole === 'EVENT_MANAGER' ? 'selected' : ''}>EVENT_MANAGER</option>
                        <option value="ADMIN" ${currentRole === 'ADMIN' ? 'selected' : ''}>ADMIN</option>
                    </select>
                </div>
                <div style="display: flex; gap: 1rem;">
                    <button type="submit" class="btn btn-success">Сохранить</button>
                    <button type="button" class="btn btn-secondary" onclick="App.closeModal()">Отмена</button>
                </div>
            </form>
        `);

        document.getElementById('edit-user-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            try {
                await API.updateUser({
                    id: id,
                    username: document.getElementById('edit-username').value,
                    role: document.getElementById('edit-role').value
                });
                App.closeModal();
                App.showAlert('Пользователь обновлен', 'success');
                await this.loadUsers();
            } catch (error) {
                App.showAlert('Ошибка: ' + error.message);
            }
        });
    },

    async deleteUser(id) {
        if (!confirm('Удалить пользователя?')) return;
        try {
            await API.deleteUser(id);
            App.showAlert('Пользователь удален', 'success');
            await this.loadUsers();
        } catch (error) {
            App.showAlert('Ошибка: ' + error.message);
        }
    },

    async renderTowns() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h2>Управление городами</h2>
                <button class="btn btn-success" id="create-town-btn">+ Создать город</button>
            </div>
            <div id="towns-container"></div>
        `;

        document.getElementById('create-town-btn').addEventListener('click', () => this.showTownModal());
        await this.loadTowns();
    },

    async loadTowns() {
        const container = document.getElementById('towns-container');
        container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const towns = await API.getTowns();
            this.renderTownsTable(towns);
        } catch (error) {
            container.innerHTML = `<div class="alert alert-error">Ошибка: ${error.message}</div>`;
        }
    },

    renderTownsTable(towns) {
        const container = document.getElementById('towns-container');
        
        if (!towns || towns.length === 0) {
            container.innerHTML = '<div class="card"><p>Города не найдены</p></div>';
            return;
        }

        container.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Название</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    ${towns.map(t => `
                        <tr>
                            <td>${t.id}</td>
                            <td>${App.escapeHtml(t.name)}</td>
                            <td class="actions">
                                <button class="btn btn-danger btn-sm" onclick="AdminView.deleteTown(${t.id})">Удалить</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    showTownModal() {
        App.showModal(`
            <h2 class="card-title">Создание города</h2>
            <form id="town-form">
                <div class="form-group">
                    <label>Название *</label>
                    <input type="text" id="town-name" required placeholder="Москва">
                </div>
                <div style="display: flex; gap: 1rem;">
                    <button type="submit" class="btn btn-success">Создать</button>
                    <button type="button" class="btn btn-secondary" onclick="App.closeModal()">Отмена</button>
                </div>
            </form>
        `);

        document.getElementById('town-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            try {
                await API.createTown({ name: document.getElementById('town-name').value });
                App.closeModal();
                App.showAlert('Город создан', 'success');
                await this.loadTowns();
            } catch (error) {
                App.showAlert('Ошибка: ' + error.message);
            }
        });
    },

    async deleteTown(id) {
        if (!confirm('Удалить город?')) return;
        try {
            await API.deleteTown(id);
            App.showAlert('Город удален', 'success');
            await this.loadTowns();
        } catch (error) {
            App.showAlert('Ошибка: ' + error.message);
        }
    }
};