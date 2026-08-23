FROM eclipse-temurin:21-jdk AS builder

COPY ./gradle /workspace/gradle
COPY ./booking-service /workspace/booking-service

WORKDIR /workspace/booking-service
RUN chmod +x ./gradlew && ./gradlew bootJar -x test --no-daemon

FROM eclipse-temurin:21-jre
WORKDIR /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0"

COPY --from=builder /workspace/booking-service/build/libs/*.jar app.jar

EXPOSE 8082

USER appuser

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]