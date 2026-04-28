const App = window.App;
const API = window.API;

export const ResetPasswordView = {
    async render() {
        const content = document.getElementById('content');
        
        // Get token from URL
        const hash = window.location.hash;
        const tokenMatch = hash.match(/[?&]token=([^&]+)/);
        let token = tokenMatch ? decodeURIComponent(tokenMatch[1]) : null;

        // Also check if token is in the hash path itself (for #/reset-password?token=xxx format)
        if (!token) {
            const urlParams = new URLSearchParams(window.location.hash.split('?')[1] || '');
            token = urlParams.get('token');
        }

        if (!token) {
            content.innerHTML = `
                <div class="card" style="max-width: 400px; margin: 2rem auto;">
                    <h2 class="card-title">Ошибка</h2>
                    <div class="alert alert-error">
                        Неверная или отсутствующая ссылка для восстановления пароля.
                    </div>
                    <p style="margin-top: 1rem; text-align: center;">
                        <a href="#/forgot-password">Запросить новую ссылку</a>
                    </p>
                </div>
            `;
            return;
        }

        // Validate token first
        let isTokenValid = false;
        try {
            isTokenValid = await API.validateResetToken(token);
        } catch (error) {
            console.error('Token validation error:', error);
        }

        if (!isTokenValid) {
            content.innerHTML = `
                <div class="card" style="max-width: 400px; margin: 2rem auto;">
                    <h2 class="card-title">Ссылка недействительна</h2>
                    <div class="alert alert-error">
                        Ссылка для восстановления пароля истекла или недействительна.
                    </div>
                    <p style="margin-top: 1rem; text-align: center;">
                        <a href="#/forgot-password">Запросить новую ссылку</a>
                    </p>
                </div>
            `;
            return;
        }

        content.innerHTML = `
            <div class="card" style="max-width: 400px; margin: 2rem auto;">
                <h2 class="card-title">Новый пароль</h2>
                <p style="margin-bottom: 1rem; color: #666;">
                    Введите новый пароль для вашего аккаунта.
                </p>
                <form id="reset-password-form">
                    <div class="form-group">
                        <label for="password">Новый пароль</label>
                        <input type="password" id="password" required minlength="6" placeholder="Минимум 6 символов">
                    </div>
                    <div class="form-group">
                        <label for="confirm-password">Подтверждение пароля</label>
                        <input type="password" id="confirm-password" required minlength="6">
                        <small id="password-match-error" class="text-danger hidden" style="color: red;">Пароли не совпадают</small>
                    </div>
                    <div id="form-message" class="alert hidden"></div>
                    <button type="submit" class="btn btn-primary" style="width: 100%;">Сохранить пароль</button>
                </form>
            </div>
        `;

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

        document.getElementById('reset-password-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirm-password').value;
            const messageDiv = document.getElementById('form-message');
            const submitButton = e.target.querySelector('button[type="submit"]');

            // Validate passwords match
            if (password !== confirmPassword) {
                messageDiv.className = 'alert alert-error';
                messageDiv.textContent = 'Пароли не совпадают';
                messageDiv.classList.remove('hidden');
                return;
            }

            // Disable button to prevent double submission
            submitButton.disabled = true;
            submitButton.textContent = 'Сохранение...';

            try {
                await API.resetPassword(token, password);
                
                messageDiv.className = 'alert alert-success';
                messageDiv.textContent = 'Пароль успешно изменен! Теперь вы можете войти с новым паролем.';
                messageDiv.classList.remove('hidden');
                
                // Redirect to login page after 2 seconds
                setTimeout(() => {
                    App.navigate('/login');
                }, 2000);
            } catch (error) {
                messageDiv.className = 'alert alert-error';
                messageDiv.textContent = error.message || 'Ошибка при смене пароля';
                messageDiv.classList.remove('hidden');
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = 'Сохранить пароль';
            }
        });
    }
};
