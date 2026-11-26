package com.microservices_example_app.gateway;

import io.github.bonigarcia.wdm.WebDriverManager;
import jakarta.mail.*;
import jakarta.mail.internet.InternetAddress;
import jakarta.mail.internet.MimeMessage;
import jakarta.mail.internet.MimeMultipart;
import org.junit.jupiter.api.*;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Date;
import java.util.Properties;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("e2e")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class RegistrationE2ETest {

    private static WebDriver driver;

    private static final String GATEWAY_URL = "http://localhost:8080";
    private static final String FRONTEND_URL = frontendUrl();
    private static final String GMAIL_HOST = "imap.gmail.com";
    private static final int GMAIL_PORT = 993;
    private static final int EMAIL_WAIT_SECONDS = 120;

    private static String gmailUsername;
    private static String gmailPassword;
    private static String testUsername;
    private static String testPassword;

    private record EmailData(String subject, String from, String body) {}

    private static String frontendUrl() {
        String url = System.getenv("FRONTEND_URL");
        return url != null && !url.isBlank() ? url : "http://localhost:3000";
    }

    @BeforeAll
    static void setup() throws Exception {
        gmailUsername = System.getenv("GMAIL_USERNAME");
        gmailPassword = System.getenv("GMAIL_PASSWORD");
        testUsername = "e2e_user_" + System.currentTimeMillis();
        testPassword = "TestPass123!";

        if (gmailUsername == null || gmailPassword == null) {
            throw new IllegalStateException(
                    "GMAIL_USERNAME and GMAIL_PASSWORD env vars must be set");
        }

        startDockerCompose();
        startBrowser();
    }

    @AfterAll
    static void teardown() {
        if (driver != null) {
            try { driver.quit(); } catch (Exception ignored) {}
        }
        stopDockerCompose();
    }

    @Test
    @Order(1)
    @DisplayName("Register CUSTOMER via new frontend")
    void testRegisterCustomer() {
        // The new frontend registers CUSTOMER only and redirects to /profile.
        driver.get(FRONTEND_URL + "/register");

        WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(15));
        wait.until(ExpectedConditions.presenceOfElementLocated(
                By.cssSelector("[data-testid='register-submit']")));

        setValue("[data-testid='register-name']", testUsername);
        setValue("[data-testid='register-email']", gmailUsername);
        setValue("[data-testid='register-password']", testPassword);
        setValue("[data-testid='register-confirm']", testPassword);

        driver.findElement(By.cssSelector("[data-testid='register-submit']")).click();

        WebDriverWait navWait = new WebDriverWait(driver, Duration.ofSeconds(30));
        navWait.until(d -> d.getCurrentUrl().contains("/profile"));

        assertThat(driver.getCurrentUrl()).contains("/profile");
        WebElement profile = navWait.until(
                ExpectedConditions.presenceOfElementLocated(
                        By.cssSelector("[data-testid='profile-page']")));
        assertThat(profile).isNotNull();
    }

    private static void setValue(String cssSelector, String value) {
        WebElement input = driver.findElement(By.cssSelector(cssSelector));
        input.clear();
        input.sendKeys(value);
    }

    @Test
    @Order(2)
    @DisplayName("Verify registration email arrived in Gmail via IMAP")
    void testGmailReceivedRegistrationEmail() throws Exception {
        EmailData email = waitForEmail(
                gmailUsername, gmailPassword,
                "Registration successful", testUsername,
                EMAIL_WAIT_SECONDS);

        assertThat(email).as("Registration email should arrive in Gmail").isNotNull();
        assertThat(email.subject()).isEqualTo("Registration successful");
        assertThat(email.body()).contains("Hello, " + testUsername + "!");
        assertThat(email.body()).contains("registration was completed successfully");
        assertThat(email.from()).isEqualTo(gmailUsername);
    }

    private EmailData waitForEmail(String username, String password,
                                   String subjectContains, String expectedUsername,
                                   int timeoutSeconds)
            throws Exception {
        long deadline = System.currentTimeMillis() + (timeoutSeconds * 1000L);

        while (System.currentTimeMillis() < deadline) {
            EmailData found = searchEmail(username, password, subjectContains, expectedUsername);
            if (found != null) {
                return found;
            }
            Thread.sleep(5000);
        }
        return null;
    }

    private EmailData searchEmail(String username, String password,
                                  String subjectContains, String expectedUsername) {
        Properties props = new Properties();
        props.put("mail.store.protocol", "imaps");
        props.put("mail.imaps.host", GMAIL_HOST);
        props.put("mail.imaps.port", String.valueOf(GMAIL_PORT));
        props.put("mail.imaps.ssl.enable", "true");
        props.put("mail.imaps.ssl.trust", GMAIL_HOST);

        Session session = Session.getInstance(props);
        Store store = null;
        Folder inbox = null;

        try {
            store = session.getStore("imaps");
            store.connect(GMAIL_HOST, username, password);

            inbox = store.getFolder("INBOX");
            inbox.open(Folder.READ_ONLY);

            long fiveMinutesAgo = System.currentTimeMillis() - (5 * 60 * 1000L);
            Date since = new Date(fiveMinutesAgo);
            jakarta.mail.search.ReceivedDateTerm dateTerm =
                    new jakarta.mail.search.ReceivedDateTerm(
                            jakarta.mail.search.ComparisonTerm.GE, since);
            jakarta.mail.search.SubjectTerm subjectTerm =
                    new jakarta.mail.search.SubjectTerm(subjectContains);
            jakarta.mail.search.AndTerm searchTerm =
                    new jakarta.mail.search.AndTerm(subjectTerm, dateTerm);

            Message[] messages = inbox.search(searchTerm);

            for (Message message : messages) {
                MimeMessage msg = (MimeMessage) message;
                String subject = msg.getSubject();
                String from = "";
                if (msg.getFrom() != null && msg.getFrom().length > 0) {
                    from = ((InternetAddress) msg.getFrom()[0]).getAddress();
                }
                String body = extractText(msg);
                if (expectedUsername == null || body.contains("Hello, " + expectedUsername + "!")) {
                    return new EmailData(subject, from, body);
                }
            }
            return null;
        } catch (Exception e) {
            System.err.println("IMAP search error: " + e.getMessage());
            return null;
        } finally {
            try {
                if (inbox != null && inbox.isOpen()) inbox.close(true);
                if (store != null) store.close();
            } catch (Exception ignored) {}
        }
    }

    private String extractText(MimeMessage message) throws Exception {
        if (message.isMimeType("text/plain")) {
            return (String) message.getContent();
        }
        if (message.isMimeType("text/html")) {
            return (String) message.getContent();
        }
        if (message.isMimeType("multipart/*")) {
            MimeMultipart multipart = (MimeMultipart) message.getContent();
            for (int i = 0; i < multipart.getCount(); i++) {
                BodyPart bodyPart = multipart.getBodyPart(i);
                if (bodyPart.isMimeType("text/plain")) {
                    return (String) bodyPart.getContent();
                }
                if (bodyPart.isMimeType("text/html")) {
                    return (String) bodyPart.getContent();
                }
            }
        }
        return message.getContent().toString();
    }

    private static void startDockerCompose() throws Exception {
        ProcessBuilder pb = new ProcessBuilder(
                "docker", "compose", "up", "-d", "--build");
        pb.directory(Path.of("..").toFile());
        pb.redirectErrorStream(true);
        Process process = pb.start();
        String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        int exitCode = process.waitFor();
        if (exitCode != 0) {
            throw new RuntimeException("docker compose up failed:\n" + output);
        }

        waitForServicesHealthy();
    }

    private static void waitForServicesHealthy() throws Exception {
        waitForUrl(GATEWAY_URL, "Gateway", 180_000L);
        // Frontend proxies /users and /booking to the gateway, so check it last.
        waitForUrl(FRONTEND_URL, "Frontend", 180_000L);
    }

    private static void waitForUrl(String url, String name, long timeoutMs) throws Exception {
        System.out.println("Waiting for " + name + " at " + url + "...");
        long deadline = System.currentTimeMillis() + timeoutMs;

        while (System.currentTimeMillis() < deadline) {
            ProcessBuilder httpCheck = new ProcessBuilder(
                    "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    url);
            httpCheck.redirectErrorStream(true);
            Process httpProcess = httpCheck.start();
            String httpCode = new String(httpProcess.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();
            httpProcess.waitFor();

            if (httpCode.equals("200")) {
                System.out.println(name + " is healthy!");
                Thread.sleep(3000);
                return;
            }

            System.out.print(".");
            Thread.sleep(5000);
        }
        throw new RuntimeException(name + " did not become healthy within timeout");
    }

    private static void stopDockerCompose() {
        try {
            ProcessBuilder pb = new ProcessBuilder(
                    "docker", "compose", "down", "-v");
            pb.directory(Path.of("..").toFile());
            pb.redirectErrorStream(true);
            Process process = pb.start();
            process.waitFor();
            System.out.println("Docker Compose stopped.");
        } catch (Exception e) {
            System.err.println("Failed to stop Docker Compose: " + e.getMessage());
        }
    }

    private static void startBrowser() {
        WebDriverManager.chromedriver().setup();
        ChromeOptions options = new ChromeOptions();
        options.addArguments("--headless=new");
        options.addArguments("--no-sandbox");
        options.addArguments("--disable-dev-shm-usage");
        options.addArguments("--disable-gpu");
        options.addArguments("--window-size=1920,1080");
        options.addArguments("--lang=ru-RU");
        driver = new ChromeDriver(options);
        driver.manage().timeouts().pageLoadTimeout(Duration.ofSeconds(30));
        driver.manage().timeouts().scriptTimeout(Duration.ofSeconds(15));
    }
}
