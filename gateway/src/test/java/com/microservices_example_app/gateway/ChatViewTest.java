package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ChatViewTest extends SeleniumTestBase {

    private void openChat() {
        navigateTo("/");
        clickByTestId("assistant-fab");
        assertThat(findByTestId("chat-panel")).isNotNull();
    }

    @Test
    void shouldOpenChatPanelFromFab() {
        openChat();
        assertThat(findByTestId("chat-input")).isNotNull();
        assertThat(findByTestId("chat-send")).isNotNull();
    }

    @Test
    void shouldShowChatHeader() {
        openChat();
        assertThat(find(".chat-panel header h2").getText()).isEqualTo("Ваш помощник");
    }

    @Test
    void shouldCloseChatPanel() {
        openChat();
        clickByTestId("chat-close");
        new org.openqa.selenium.support.ui.WebDriverWait(driver, java.time.Duration.ofSeconds(10))
                .until(d -> d.findElements(org.openqa.selenium.By.cssSelector("[data-testid='chat-panel']")).isEmpty());
    }

    @Test
    void shouldEchoUserMessage() {
        openChat();
        typeByTestId("chat-input", "Что-нибудь на выходные");
        clickByTestId("chat-send");
        assertThat(findByTestId("chat-user-message").getText())
                .isEqualTo("Что-нибудь на выходные");
    }

    @Test
    void shouldShowErrorWithoutBackend() {
        openChat();
        typeByTestId("chat-input", "Тихий джаз в субботу");
        clickByTestId("chat-send");
        // No backend behind the static export: the panel must say so.
        assertThat(findByTestId("chat-error").getText()).contains("ассистент");
    }

    @Test
    void shouldShowPlanRequestButton() {
        openChat();
        assertThat(findByTestId("chat-plan-request")).isNotNull();
    }
}
