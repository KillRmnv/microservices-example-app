const App = window.App;
const API = window.API;

export const ForgetPasswordView = {
    render() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div class="card" style="max-width: 400px; margin: 2rem auto;">
                <h2 class="card-title">Восстановление пароля</h2>
                <p style="margin-bottom: 1rem; color: #666;">
                    Введите ваш email, и мы отправим вам ссылку для восстановления пароля.
                </p>
                <form id="forget-password-form">
                    <div class="form-group">
                        <label for="email">Email</label>
                        <input type="email" id="email" required placeholder="example@mail.com">
                    </div>
                    <div id="form-message" class="alert hidden"></div>
                    <button type="submit" class="btn btn-primary" style="width: 100%;">Отправить</button>
                </form>
                <p style="margin-top: 1rem; text-align: center;">
                    <a href="#/login">Вернуться к входу</a>
                </p>
            </div>
        `;

        document.getElementById('forget-password-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const messageDiv = document.getElementById('form-message');
            const submitButton = e.target.querySelector('button[type="submit"]');

            // Disable button to prevent double submission
            submitButton.disabled = true;
            submitButton.textContent = 'Отправка...';

            try {
                await API.forgetPassword(email);
                messageDiv.className = 'alert alert-success';
                messageDiv.textContent = 'Ссылка для восстановления пароля отправлена на ваш email.';
                messageDiv.classList.remove('hidden');
                
                // Clear the form
                document.getElementById('email').value = '';
            } catch (error) {
                messageDiv.className = 'alert alert-error';
                messageDiv.textContent = error.message || 'Ошибка при отправке запроса';
                messageDiv.classList.remove('hidden');
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = 'Отправить';
            }
        });
    }
};
