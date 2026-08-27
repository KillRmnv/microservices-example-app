package com.microservices_example_app.gateway;

import io.github.bonigarcia.wdm.WebDriverManager;
import jakarta.mail.*;
import jakarta.mail.internet.InternetAddress;
import jakarta.mail.internet.MimeMessage;
import jakarta.mail.internet.MimeMultipart;
import org.junit.jupiter.api.*;
import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Date;
import java.util.Properties;

import com.sun.net.httpserver.HttpServer;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("e2e")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class RegistrationE2ETest {

    private static WebDriver driver;
    private static HttpServer server;

    private static final Path STATIC_DIR = Path.of("src/main/resources/static");
    private static final String GATEWAY_URL = "http://localhost:8080";
    private static final String GMAIL_HOST = "imap.gmail.com";
    private static final int GMAIL_PORT = 993;
    private static final int EMAIL_WAIT_SECONDS = 120;

    private static String gmailUsername;
    private static String gmailPassword;
    private static String testUsername;
    private static String testPassword;

    private record EmailData(String subject, String from, String body) {}

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
        startStaticServer();
    }

    @AfterAll
    static void teardown() {
        if (driver != null) {
            try { driver.quit(); } catch (Exception ignored) {}
        }
        if (server != null) {
            server.stop(0);
        }
        stopDockerCompose();
    }

    @Test
    @Order(1)
    @DisplayName("Register CUSTOMER via gateway frontend")
    void testRegisterCustomer() {
        driver.get(GATEWAY_URL);
        waitForPageLoad();

        ((JavascriptExecutor) driver).executeScript("window.location.hash = '/register'");
        waitForPageLoad();

        WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(10));
        wait.until(ExpectedConditions.presenceOfElementLocated(By.id("register-form")));

        WebElement usernameInput = driver.findElement(By.id("username"));
        WebElement emailInput = driver.findElement(By.id("email"));
        WebElement passwordInput = driver.findElement(By.id("password"));
        WebElement confirmPasswordInput = driver.findElement(By.id("confirm-password"));

        usernameInput.clear();
        usernameInput.sendKeys(testUsername);

        emailInput.clear();
        emailInput.sendKeys(gmailUsername);

        passwordInput.clear();
        passwordInput.sendKeys(testPassword);

        confirmPasswordInput.clear();
        confirmPasswordInput.sendKeys(testPassword);

        waitForPageLoad();

        ((JavascriptExecutor) driver).executeScript(
                "document.getElementById('role').value = 'CUSTOMER'");

        waitForPageLoad();

        WebElement submitBtn = driver.findElement(By.cssSelector("#register-form button[type='submit']"));
        submitBtn.click();

        WebDriverWait navWait = new WebDriverWait(driver, Duration.ofSeconds(15));
        navWait.until(d -> {
            String hash = (String) ((JavascriptExecutor) d).executeScript("return window.location.hash");
            return hash != null && hash.contains("/login");
        });

        String currentHash = (String) ((JavascriptExecutor) driver)
                .executeScript("return window.location.hash");
        assertThat(currentHash).contains("/login");
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
        System.out.println("Waiting for services to become healthy...");
        long deadline = System.currentTimeMillis() + 180_000L;

        while (System.currentTimeMillis() < deadline) {
            ProcessBuilder httpCheck = new ProcessBuilder(
                    "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    GATEWAY_URL);
            httpCheck.redirectErrorStream(true);
            Process httpProcess = httpCheck.start();
            String httpCode = new String(httpProcess.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();
            httpProcess.waitFor();

            if (httpCode.equals("200")) {
                System.out.println("Gateway is healthy!");
                Thread.sleep(3000);
                return;
            }

            System.out.print(".");
            Thread.sleep(5000);
        }
        throw new RuntimeException("Gateway did not become healthy within timeout");
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

    private static void startStaticServer() throws Exception {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/", exchange -> {
            String path = exchange.getRequestURI().getPath();
            if (path.equals("/")) path = "/index.html";

            Path file = STATIC_DIR.resolve(path.substring(1));
            if (Files.exists(file) && !Files.isDirectory(file)) {
                byte[] bytes = Files.readAllBytes(file);
                String contentType = guessContentType(path);
                exchange.getResponseHeaders().set("Content-Type", contentType + "; charset=UTF-8");
                exchange.sendResponseHeaders(200, bytes.length);
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(bytes);
                }
            } else {
                byte[] notFound = "Not Found".getBytes();
                exchange.sendResponseHeaders(404, notFound.length);
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(notFound);
                }
            }
        });
        server.start();
    }

    private void waitForPageLoad() {
        try { Thread.sleep(1000); } catch (InterruptedException ignored) {}
    }

    private static String guessContentType(String path) {
        if (path.endsWith(".html")) return "text/html";
        if (path.endsWith(".js")) return "application/javascript";
        if (path.endsWith(".css")) return "text/css";
        if (path.endsWith(".json")) return "application/json";
        return "application/octet-stream";
    }
}
