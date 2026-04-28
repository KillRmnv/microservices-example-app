FROM eclipse-temurin:25-jdk AS builder

COPY ./gradle /workspace/gradle
COPY ./gateway /workspace/gateway


WORKDIR /workspace/gateway
RUN chmod +x ./gradlew && ./gradlew bootJar -x test --no-daemon

FROM eclipse-temurin:25-jre
WORKDIR /app

ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0"

COPY --from=builder /workspace/gateway/build/libs/*.jar app.jar


EXPOSE 8080

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]