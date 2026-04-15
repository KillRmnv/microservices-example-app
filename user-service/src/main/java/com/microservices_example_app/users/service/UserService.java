package com.microservices_example_app.users.service;

import com.microservices_example_app.users.dto.UserRegistrationDto;
import com.microservices_example_app.users.dto.UserResponseDto;
import com.microservices_example_app.users.model.Role;
import com.microservices_example_app.users.model.User;
import com.microservices_example_app.users.repository.RoleRepository;
import com.microservices_example_app.users.repository.UserRepository;
import com.microservices_example_app.users.utils.JwtUtil;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class UserService {

    private final UserRepository userDao;
    private final RoleRepository roleRepository;
    private final PasswordService passwordService;

    public UserService(UserRepository userDao, RoleRepository roleRepository, PasswordService passwordService) {
        this.userDao = userDao;
        this.roleRepository = roleRepository;
        this.passwordService = passwordService;
    }

    @Transactional
    public UserResponseDto register(UserRegistrationDto dto) {
        Role customerRole = roleRepository.findByName("CUSTOMER")
                .orElseThrow(() -> new IllegalStateException("Default role CUSTOMER not found"));

        String hash = passwordService.hash(dto.getPassword());

        User user = User.builder()
                .username(dto.getUsername())
                .email(dto.getEmail())
                .passwordHash(hash)
                .userRole(customerRole)
                .build();

        User saved = userDao.save(user);

        return toResponseDto(saved);
    }

    @Transactional(readOnly = true)
    public String login(String email, String password) {
        User user = userDao.findByEmail(email)
                .orElseThrow(() -> new IllegalArgumentException("Invalid email or password"));

        if (!passwordService.verify(password, user.getPasswordHash())) {
            throw new IllegalArgumentException("Invalid email or password");
        }

        return JwtUtil.generateToken(
                user.getUsername(),
                user.getEmail(),
                user.getUserRole().getName()
        );
    }

    @Transactional(readOnly = true)
    public UserResponseDto getByEmail(String email) {
        User user = userDao.findByEmail(email)
                .orElseThrow(() -> new IllegalArgumentException("User not found: " + email));

        return toResponseDto(user);
    }

    private UserResponseDto toResponseDto(User user) {
        return new UserResponseDto(
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                user.getUserRole().getName()
        );
    }
}
