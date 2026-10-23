package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;
import org.openqa.selenium.WebElement;

import static org.assertj.core.api.Assertions.assertThat;

class AuthViewTest extends SeleniumTestBase {

    @Test
    void shouldRenderLoginForm() {
        navigateTo("/login");
        assertThat(findByTestId("login-email").getAttribute("type")).isEqualTo("email");
        assertThat(findByTestId("login-password").getAttribute("type")).isEqualTo("password");
        assertThat(findByTestId("login-submit").getText()).isEqualTo("Войти");
    }

    @Test
    void shouldRequireLoginInputs() {
        navigateTo("/login");
        assertThat(findByTestId("login-email").getAttribute("required")).isNotNull();
        assertThat(findByTestId("login-password").getAttribute("required")).isNotNull();
    }

    @Test
    void shouldLinkRegisterAndForgotPasswordFromLogin() {
        navigateTo("/login");
        assertThat(find("a[href='/register']").getText()).isEqualTo("Оформить");
        assertThat(find("a[href='/forgot-password']").getText()).isEqualTo("Забыли пароль?");
    }

    @Test
    void shouldRenderRegisterForm() {
        navigateTo("/register");
        assertThat(findByTestId("register-name")).isNotNull();
        assertThat(findByTestId("register-email").getAttribute("type")).isEqualTo("email");
        assertThat(findByTestId("register-password").getAttribute("type")).isEqualTo("password");
        assertThat(findByTestId("register-confirm").getAttribute("type")).isEqualTo("password");
        assertThat(findByTestId("register-submit").getText()).isEqualTo("Зарегистрироваться");
    }

    @Test
    void shouldRequirePasswordMinLengthOnRegister() {
        navigateTo("/register");
        assertThat(findByTestId("register-password").getAttribute("minlength")).isEqualTo("6");
        assertThat(findByTestId("register-confirm").getAttribute("minlength")).isEqualTo("6");
    }

    @Test
    void shouldShowPasswordMismatchErrorWithoutBackend() {
        navigateTo("/register");
        findByTestId("register-name").sendKeys("Читатель");
        findByTestId("register-email").sendKeys("reader@mail.com");
        findByTestId("register-password").sendKeys("secret123");
        findByTestId("register-confirm").sendKeys("other123");
        findByTestId("register-submit").click();
        assertThat(find(".auth-error").getText()).isEqualTo("Пароли не совпадают");
    }

    @Test
    void shouldLinkLoginFromRegister() {
        navigateTo("/register");
        assertThat(find("a[href='/login']").getText()).contains("Войти");
    }

    @Test
    void shouldRenderForgotPasswordForm() {
        navigateTo("/forgot-password");
        assertThat(findByTestId("forgot-email").getAttribute("type")).isEqualTo("email");
        assertThat(findByTestId("forgot-submit").getText()).isEqualTo("Отправить ссылку");
    }

    @Test
    void shouldRenderResetPasswordForm() {
        navigateTo("/reset-password");
        assertThat(findByTestId("reset-token")).isNotNull();
        assertThat(findByTestId("reset-password").getAttribute("type")).isEqualTo("password");
        assertThat(findByTestId("reset-confirm").getAttribute("type")).isEqualTo("password");
        assertThat(findByTestId("reset-submit").getText()).isEqualTo("Сохранить пароль");
    }

    @Test
    void shouldShowMastheadOnLoginPage() {
        navigateTo("/login");
        WebElement brand = find(".auth-logo");
        assertThat(brand.getText()).isEqualTo("ДОСУГ");
    }
}
