package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;
import org.openqa.selenium.WebElement;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class AuthViewTest extends SeleniumTestBase {

    @Test
    void shouldRenderLoginForm() {
        navigateTo("/login");
        assertThat(find("#login-form")).isNotNull();
    }

    @Test
    void shouldHaveLoginEmailInput() {
        navigateTo("/login");
        WebElement email = find("#email");
        assertThat(email.getAttribute("type")).isEqualTo("email");
    }

    @Test
    void shouldHaveLoginPasswordInput() {
        navigateTo("/login");
        WebElement password = find("#password");
        assertThat(password.getAttribute("type")).isEqualTo("password");
    }

    @Test
    void shouldHaveLoginSubmitButton() {
        navigateTo("/login");
        WebElement btn = find("#login-form button[type='submit']");
        assertThat(btn.getText()).isEqualTo("Войти");
    }

    @Test
    void shouldHaveLoginErrorDiv() {
        navigateTo("/login");
        WebElement errorDiv = find("#login-error");
        assertThat(errorDiv.getAttribute("class")).contains("hidden");
    }

    @Test
    void shouldHaveForgotPasswordLink() {
        navigateTo("/login");
        WebElement link = find("a[href='#/forgot-password']");
        assertThat(link.getText()).isEqualTo("Забыли пароль?");
    }

    @Test
    void shouldHaveRegisterLink() {
        navigateTo("/login");
        WebElement link = find("a[href='#/register']");
        assertThat(link.getText()).isEqualTo("Зарегистрироваться");
    }

    @Test
    void shouldHaveLoginFormTitle() {
        navigateTo("/login");
        assertThat(find(".card-title").getText()).isEqualTo("Вход в систему");
    }

    @Test
    void shouldHaveFormGroups() {
        navigateTo("/login");
        List<WebElement> groups = findAll(".form-group");
        assertThat(groups).hasSize(2);
    }

    @Test
    void shouldHaveLoginLabels() {
        navigateTo("/login");
        List<WebElement> labels = findAll("#login-form label");
        assertThat(labels).hasSize(2);
        assertThat(labels.get(0).getText()).isEqualTo("Email");
        assertThat(labels.get(1).getText()).isEqualTo("Пароль");
    }

    @Test
    void shouldRenderRegisterForm() {
        navigateTo("/register");
        assertThat(find("#register-form")).isNotNull();
    }

    @Test
    void shouldHaveRegisterUsernameInput() {
        navigateTo("/register");
        WebElement username = find("#username");
        assertThat(username.getAttribute("type")).isEqualTo("text");
    }

    @Test
    void shouldHaveRegisterEmailInput() {
        navigateTo("/register");
        WebElement email = find("#email");
        assertThat(email.getAttribute("type")).isEqualTo("email");
    }

    @Test
    void shouldHaveRegisterPasswordInput() {
        navigateTo("/register");
        WebElement password = find("#password");
        assertThat(password.getAttribute("type")).isEqualTo("password");
    }

    @Test
    void shouldHaveConfirmPasswordInput() {
        navigateTo("/register");
        WebElement confirmPassword = find("#confirm-password");
        assertThat(confirmPassword.getAttribute("type")).isEqualTo("password");
    }

    @Test
    void shouldHaveRoleSelect() {
        navigateTo("/register");
        assertThat(find("#role")).isNotNull();
    }

    @Test
    void shouldHaveRegisterSubmitButton() {
        navigateTo("/register");
        WebElement btn = find("#register-form button[type='submit']");
        assertThat(btn.getText()).isEqualTo("Зарегистрироваться");
    }

    @Test
    void shouldHaveRegisterErrorDiv() {
        navigateTo("/register");
        WebElement errorDiv = find("#register-error");
        assertThat(errorDiv.getAttribute("class")).contains("hidden");
    }

    @Test
    void shouldHavePasswordMatchError() {
        navigateTo("/register");
        assertThat(find("#password-match-error").getAttribute("textContent")).isEqualTo("Пароли не совпадают");
    }

    @Test
    void shouldHaveRegisterTitle() {
        navigateTo("/register");
        assertThat(find(".card-title").getText()).isEqualTo("Регистрация");
    }

    @Test
    void shouldHaveLoginLinkOnRegister() {
        navigateTo("/register");
        WebElement link = find("a[href='#/login']");
        assertThat(link.getText()).isEqualTo("Войти");
    }

    @Test
    void shouldHaveUsernameMinLength() {
        navigateTo("/register");
        assertThat(find("#username").getAttribute("minlength")).isEqualTo("3");
    }

    @Test
    void shouldHavePasswordMinLength() {
        navigateTo("/register");
        assertThat(find("#password").getAttribute("minlength")).isEqualTo("6");
    }

    @Test
    void shouldHaveEmailRequired() {
        navigateTo("/login");
        assertThat(find("#email").getAttribute("required")).isNotNull();
    }

    @Test
    void shouldHavePasswordRequired() {
        navigateTo("/login");
        assertThat(find("#password").getAttribute("required")).isNotNull();
    }

    @Test
    void shouldHaveForgotPasswordForm() {
        navigateTo("/forgot-password");
        assertThat(find(".card")).isNotNull();
    }

    @Test
    void shouldHaveResetPasswordForm() {
        navigateTo("/reset-password");
        assertThat(find(".card")).isNotNull();
    }

    @Test
    void shouldShowNavLinksOnLoginPage() {
        navigateTo("/login");
        List<WebElement> navLinks = findAll("#main-nav a");
        assertThat(navLinks).isNotEmpty();
    }

    @Test
    void shouldHaveRegisterFormLabels() {
        navigateTo("/register");
        List<WebElement> labels = findAll("#register-form label");
        assertThat(labels.size()).isGreaterThanOrEqualTo(4);
    }

    @Test
    void shouldHaveRegisterFormGroups() {
        navigateTo("/register");
        List<WebElement> groups = findAll(".form-group");
        assertThat(groups.size()).isGreaterThanOrEqualTo(5);
    }
}
