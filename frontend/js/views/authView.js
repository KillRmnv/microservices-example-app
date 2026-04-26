const AuthView = {
    renderLogin() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div class="card" style="max-width: 400px; margin: 2rem auto;">
                <h2 class="card-title">Вход в систему</h2>
                <form id="login-form">
                    <div class="form-group">
                        <label for="email">Email</label>
                        <input type="email" id="email" required>
                    </div>
                    <div class="form-group">
                        <label for="password">Пароль</label>
                        <input type="password" id="password" required>
                    </div>
                    <div id="login-error" class="alert alert-error hidden"></div>
                    <button type="submit" class="btn btn-primary" style="width: 100%;">Войти</button>
                </form>
                <p style="margin-top: 1rem; text-align: center;">
                    Нет аккаунта? <a href="#/register">Зарегистрироваться</a>
                </p>
            </div>
        `;

        document.getElementById('login-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('login-error');

            
            try {
                const response = await Auth.login(email, password);
                errorDiv.classList.add('hidden');
                App.showAlert('Вход выполнен успешно!', 'success');
                setTimeout(() => window.location.reload(), 500);
            } catch (error) {
                errorDiv.textContent = error.message || 'Ошибка входа';
                errorDiv.classList.remove('hidden');
            }
        });
    },

    renderRegister() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div class="card" style="max-width: 400px; margin: 2rem auto;">
                <h2 class="card-title">Регистрация</h2>
                <form id="register-form">
                    <div class="form-group">
                        <label for="username">Имя пользователя</label>
                        <input type="text" id="username" required minlength="3">
                    </div>
                    <div class="form-group">
                        <label for="email">Email</label>
                        <input type="email" id="email" required>
                    </div>
                    <div class="form-group">
                        <label for="password">Пароль</label>
                        <input type="password" id="password" required minlength="6">
                    </div>
                    <div class="form-group">
                        <label for="role">Роль</label>
                        <select id="role">
                            <option value="CUSTOMER">Клиент</option>
                            <option value="EVENT_MANAGER">Менеджер событий</option>
                        </select>
                    </div>
                    <div id="register-error" class="alert alert-error hidden"></div>
                    <button type="submit" class="btn btn-primary" style="width: 100%;">Зарегистрироваться</button>
                </form>
                <p style="margin-top: 1rem; text-align: center;">
                    Уже есть аккаунт? <a href="#/login">Войти</a>
                </p>
            </div>
        `;

        document.getElementById('register-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const role = document.getElementById('role').value;
            const errorDiv = document.getElementById('register-error');

            try {
                await Auth.register(email, password, username, role);
                App.showAlert('Регистрация прошла успешно! Теперь войдите.', 'success');
                App.navigate('/login');
            } catch (error) {
                errorDiv.textContent = error.message || 'Ошибка регистрации';
                errorDiv.classList.remove('hidden');
            }
        });
    }
};