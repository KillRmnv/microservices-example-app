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
    void shouldShowChatKicker() {
        openChat();
        // Kicker always names the desk; the mode suffix (ДЕМО/ОНЛАЙН)
        // depends on the build-time NEXT_PUBLIC_ASSISTANT_MOCK flag.
        assertThat(find(".chat-panel .kicker").getText()).contains("СПРАВКА РЕДАКЦИИ");
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
}
