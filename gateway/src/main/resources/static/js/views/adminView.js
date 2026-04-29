const App = window.App;

export const AdminView = {
    async renderUsers() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h2>Управление пользователями</h2>
                <button class="btn btn-success" id="create-user-btn">+ Создать пользователя</button>
            </div>
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

        document.getElementById('create-user-btn').addEventListener('click', () => AdminView.showCreateUserModal());
        document.getElementById('search-btn').addEventListener('click', () => AdminView.loadUsers());
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
                        <th>Имя</th>
                        <th>Email</th>
                        <th>Роль</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    ${users.map(u => `
                        <tr>
                            <td>${App.escapeHtml(u.username)}</td>
                            <td>${App.escapeHtml(u.email)}</td>
                            <td><span class="badge badge-${(u.role || 'customer').toLowerCase()}">${u.role || '-'}</span></td>
                            <td class="actions">
                                <button class="btn btn-secondary btn-sm edit-user" data-id="${u.id}" data-username="${App.escapeHtml(u.username)}" data-role="${u.role}">Ред.</button>
                                <button class="btn btn-danger btn-sm delete-user" data-id="${u.id}">Удалить</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        // Привязываем обработчики после рендера
        container.querySelectorAll('.edit-user').forEach(button => {
            button.addEventListener('click', () => {
                const id = parseInt(button.dataset.id);
                const username = button.dataset.username;
                const role = button.dataset.role;
                AdminView.showEditUserModal(id, username, role);
            });
        });

        container.querySelectorAll('.delete-user').forEach(button => {
            button.addEventListener('click', () => {
                const id = parseInt(button.dataset.id);
                AdminView.deleteUser(id);
            });
        });
    },

    showEditUserModal(id, username, currentRole) {
        App.showModal(`
            <h2 class="card-title">Редактирование пользователя</h2>
            <form id="edit-user-form">
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
                <div id="form-error" class="alert alert-error hidden"></div>
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
                await AdminView.loadUsers();
            } catch (error) {
                const errorDiv = document.getElementById('form-error');
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('hidden');
            }
        });
    },

    showCreateUserModal() {
        App.showModal(`
            <h2 class="card-title">Создание пользователя</h2>
            <form id="create-user-form">
                <div class="form-group">
                    <label>Email *</label>
                    <input type="email" id="create-email" required placeholder="user@example.com">
                </div>
                <div class="form-group">
                    <label>Имя пользователя *</label>
                    <input type="text" id="create-username" required placeholder="username">
                </div>
                <div class="form-group">
                    <label>Пароль *</label>
                    <input type="password" id="create-password" required placeholder="минимум 6 символов">
                </div>
                <div class="form-group">
                    <label>Роль</label>
                    <select id="create-role">
                        <option value="CUSTOMER">CUSTOMER</option>
                        <option value="EVENT_MANAGER">EVENT_MANAGER</option>
                        <option value="ADMIN">ADMIN</option>
                    </select>
                </div>
                <div id="form-error" class="alert alert-error hidden"></div>
                <div style="display: flex; gap: 1rem;">
                    <button type="submit" class="btn btn-success">Создать</button>
                    <button type="button" class="btn btn-secondary" onclick="App.closeModal()">Отмена</button>
                </div>
            </form>
        `);

        document.getElementById('create-user-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('create-email').value;
            const username = document.getElementById('create-username').value;
            const password = document.getElementById('create-password').value;
            const role = document.getElementById('create-role').value;

            if (!email || !username || !password) {
                const errorDiv = document.getElementById('form-error');
                errorDiv.textContent = 'Заполните все обязательные поля';
                errorDiv.classList.remove('hidden');
                return;
            }

            try {
                await API.register(email, password, username, role);
                App.closeModal();
                App.showAlert('Пользователь создан', 'success');
                await AdminView.loadUsers();
            } catch (error) {
                const errorDiv = document.getElementById('form-error');
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('hidden');
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

        document.getElementById('create-town-btn').addEventListener('click', () => AdminView.showTownModal());
        await AdminView.loadTowns();
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
                        <th>Название</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    ${towns.map(t => `
                        <tr>
                            <td>${App.escapeHtml(t.name)}</td>
                            <td class="actions">
                                <button class="btn btn-secondary btn-sm edit-town" data-id="${t.id}" data-name="${App.escapeHtml(t.name)}">Ред.</button>
                                <button class="btn btn-danger btn-sm delete-town" data-id="${t.id}">Удалить</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        // Привязываем обработчики после рендера
        container.querySelectorAll('.edit-town').forEach(button => {
            button.addEventListener('click', () => {
                const id = parseInt(button.dataset.id);
                const name = button.dataset.name;
                AdminView.showEditTownModal(id, name);
            });
        });

        container.querySelectorAll('.delete-town').forEach(button => {
            button.addEventListener('click', () => {
                const id = parseInt(button.dataset.id);
                AdminView.deleteTown(id);
            });
        });
    },

    showTownModal() {
        App.showModal(`
            <h2 class="card-title">Создание города</h2>
            <form id="town-form">
                <div class="form-group">
                    <label>Название *</label>
                    <input type="text" id="town-name" required placeholder="Москва">
                </div>
                <div id="form-error" class="alert alert-error hidden"></div>
                <div style="display: flex; gap: 1rem;">
                    <button type="submit" class="btn btn-success">Создать</button>
                    <button type="button" class="btn btn-secondary" onclick="App.closeModal()">Отмена</button>
                </div>
            </form>
        `);

        document.getElementById('town-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = document.getElementById('town-name').value;
            
            if (!name) {
                const errorDiv = document.getElementById('form-error');
                errorDiv.textContent = 'Введите название города';
                errorDiv.classList.remove('hidden');
                return;
            }

            try {
                await API.createTown({ name });
                App.closeModal();
                App.showAlert('Город создан', 'success');
                await AdminView.loadTowns();
            } catch (error) {
                const errorDiv = document.getElementById('form-error');
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('hidden');
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
    },

    showEditTownModal(id, name) {
        App.showModal(`
            <h2 class="card-title">Редактирование города</h2>
            <form id="edit-town-form">
                <div class="form-group">
                    <label>Название *</label>
                    <input type="text" id="edit-town-name" value="${App.escapeHtml(name)}" required>
                </div>
                <div id="form-error" class="alert alert-error hidden"></div>
                <div style="display: flex; gap: 1rem;">
                    <button type="submit" class="btn btn-success">Сохранить</button>
                    <button type="button" class="btn btn-secondary" onclick="App.closeModal()">Отмена</button>
                </div>
            </form>
        `);

        document.getElementById('edit-town-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            try {
                await API.updateTown({
                    id: id,
                    name: document.getElementById('edit-town-name').value
                });
                App.closeModal();
                App.showAlert('Город обновлен', 'success');
                await AdminView.loadTowns();
            } catch (error) {
                const errorDiv = document.getElementById('form-error');
                errorDiv.textContent = error.message;
                errorDiv.classList.remove('hidden');
            }
        });
    }
};
