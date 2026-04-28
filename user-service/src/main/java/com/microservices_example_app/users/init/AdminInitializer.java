package com.microservices_example_app.users.init;

import com.microservices_example_app.users.model.Role;
import com.microservices_example_app.users.model.User;
import com.microservices_example_app.users.repository.RoleRepository;
import com.microservices_example_app.users.repository.UserRepository;
import com.microservices_example_app.users.service.PasswordService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
@RequiredArgsConstructor
@Slf4j
public class AdminInitializer implements CommandLineRunner {

    private final UserRepository userRepository;
    private final RoleRepository roleRepository;
    private final PasswordService passwordService;

    @Value("${app.root-admin.username}")
    private String rootAdminUsername;

    @Value("${app.root-admin.email}")
    private String rootAdminEmail;

    @Value("${app.root-admin.password}")
    private String rootAdminPassword;

    @Override
    @Transactional
    public void run(String... args) {
        if (userRepository.existsByEmail(rootAdminEmail) || userRepository.existsByUsername(rootAdminUsername)) {
            log.info("Root admin already exists, initialization skipped");
            return;
        }

        Role adminRole = roleRepository.findByName("ADMIN")
                .orElseThrow(() -> new IllegalStateException("ADMIN role not found"));

        User rootAdmin = User.builder()
                .username(rootAdminUsername)
                .email(rootAdminEmail)
                .passwordHash(passwordService.hash(rootAdminPassword))
                .userRole(adminRole)
                .isSystem(true)
                .build();

        userRepository.save(rootAdmin);
        log.info("Root admin created successfully: {}", rootAdminEmail);
    }
}