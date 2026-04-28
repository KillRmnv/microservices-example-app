const App = window.App;
const API = window.API;

export const AuthView = {
    async renderLogin() {
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
                    <a href="#/forgot-password">Забыли пароль?</a>
                </p>
                <p style="margin-top: 0.5rem; text-align: center;">
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
                App.updateAuthUI();
                setTimeout(() => App.navigate('/'), 500);
            } catch (error) {
                errorDiv.textContent = error.message || 'Ошибка входа';
                errorDiv.classList.remove('hidden');
            }
        });
    },

    async renderRegister() {
        // Fetch available roles from backend
        let roles = [];
        try {
            roles = await API.getRoles();
            // Filter out ADMIN role - regular users cannot self-register as admin
            roles = roles.filter(role => role.name !== 'ADMIN');
        } catch (error) {
            console.error('Failed to load roles:', error);
            // Fallback to default roles if API fails
            roles = [
                { name: 'CUSTOMER', id: 1 },
                { name: 'EVENT_MANAGER', id: 2 }
            ];
        }

        const roleOptions = roles
            .map(role => `<option value="${role.name}">${this.getRoleDisplayName(role.name)}</option>`)
            .join('');

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
                        <label for="confirm-password">Подтверждение пароля</label>
                        <input type="password" id="confirm-password" required minlength="6">
                        <small id="password-match-error" class="text-danger hidden" style="color: red;">Пароли не совпадают</small>
                    </div>
                    <div class="form-group">
                        <label for="role">Роль</label>
                        <select id="role">
                            ${roleOptions}
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

        // Add real-time password match validation
        const passwordInput = document.getElementById('password');
        const confirmPasswordInput = document.getElementById('confirm-password');
        const passwordMatchError = document.getElementById('password-match-error');

        const validatePasswordMatch = () => {
            if (confirmPasswordInput.value && passwordInput.value !== confirmPasswordInput.value) {
                passwordMatchError.classList.remove('hidden');
                return false;
            } else {
                passwordMatchError.classList.add('hidden');
                return true;
            }
        };

        passwordInput.addEventListener('input', validatePasswordMatch);
        confirmPasswordInput.addEventListener('input', validatePasswordMatch);

        document.getElementById('register-form').addEventListener('submit', async (e) => {
            e.preventDefault();

            const username = document.getElementById('username').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirm-password').value;
            const role = document.getElementById('role').value;
            const errorDiv = document.getElementById('register-error');

            // Validate passwords match
            if (password !== confirmPassword) {
                errorDiv.textContent = 'Пароли не совпадают';
                errorDiv.classList.remove('hidden');
                return;
            }

            try {
                await Auth.register(email, password, username, role);
                App.showAlert('Регистрация прошла успешно! Теперь войдите.', 'success');
                App.navigate('/login');
            } catch (error) {
                errorDiv.textContent = error.message || 'Ошибка регистрации';
                errorDiv.classList.remove('hidden');
            }
        });
    },

    getRoleDisplayName(roleName) {
        const roleNames = {
            'CUSTOMER': 'Клиент',
            'EVENT_MANAGER': 'Менеджер событий',
            'ADMIN': 'Администратор'
        };
        return roleNames[roleName] || roleName;
    }
};
