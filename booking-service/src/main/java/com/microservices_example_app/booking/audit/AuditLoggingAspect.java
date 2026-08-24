package com.microservices_example_app.booking.audit;

import com.microservices_example_app.booking.utils.JwtRequestUserExtractor;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Pointcut;
import org.springframework.stereotype.Component;

@Aspect
@Component
@RequiredArgsConstructor
@Slf4j
public class AuditLoggingAspect {

    private final HttpServletRequest request;

    @Pointcut("execution(* com.microservices_example_app.booking.service.*.create*(..)) || " +
              "execution(* com.microservices_example_app.booking.service.*.update*(..)) || " +
              "execution(* com.microservices_example_app.booking.service.*.delete*(..)) || " +
              "execution(* com.microservices_example_app.booking.service.*.refund(..))")
    public void serviceWriteOperations() {}

    @Around("serviceWriteOperations()")
    public Object auditLog(ProceedingJoinPoint joinPoint) throws Throwable {
        String method = joinPoint.getSignature().getName();
        String className = joinPoint.getTarget().getClass().getSimpleName();
        String ip = request.getRemoteAddr();
        String userId = extractUserId();
        String methodHttp = request.getMethod();
        String uri = request.getRequestURI();

        log.info("AUDIT: user={} ip={} method={} uri={} operation={}.{}",
                userId, ip, methodHttp, uri, className, method);

        try {
            Object result = joinPoint.proceed();
            log.info("AUDIT-OK: user={} operation={}.{} completed", userId, className, method);
            return result;
        } catch (Throwable ex) {
            log.warn("AUDIT-FAIL: user={} operation={}.{} failed: {}", userId, className, method, ex.getMessage());
            throw ex;
        }
    }

    private String extractUserId() {
        try {
            String headerUserId = request.getHeader("X-User-Name");
            if (headerUserId != null && !headerUserId.isBlank()) {
                return headerUserId;
            }
            return "anonymous";
        } catch (Exception e) {
            return "unknown";
        }
    }
}
