package com.microservices_example_app.users.service;

import com.microservices_example_app.users.dto.*;
import com.microservices_example_app.users.exceptions.UserNotFoundException;
import com.microservices_example_app.users.model.Role;
import com.microservices_example_app.users.model.User;
import com.microservices_example_app.users.repository.RoleRepository;
import com.microservices_example_app.users.repository.UserRepository;
import com.microservices_example_app.users.utils.JwtUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Slf4j
@Service
public final class UserService {

    private final UserRepository userDao;
    private final RoleRepository roleRepository;
    private final PasswordService passwordService;

    public UserService(UserRepository userDao, RoleRepository roleRepository, PasswordService passwordService) {
        this.userDao = userDao;
        this.roleRepository = roleRepository;
        this.passwordService = passwordService;
    }

    @Transactional
    public UserRegistrationDto register(String email, String password, String role, String username) {
        log.info("Registering new user: email={}, username={}, role={}", email, username, role);

        Role customerRole = roleRepository.findByName(role)
                .orElseThrow(() -> {
                    log.warn("Registration failed: role not found, role={}", role);
                    return new IllegalStateException("Role not found");
                });

        String hash = passwordService.hash(password);

        User user = User.builder()
                .username(username)
                .email(email)
                .passwordHash(hash)
                .userRole(customerRole)
                .build();

        User saved = userDao.save(user);
        log.info("User registered successfully: id={}, email={}", saved.getId(), saved.getEmail());

        return new UserRegistrationDto(saved.getId(), saved.getUsername(), saved.getEmail());
    }

    @Transactional(readOnly = true)
    public UserLoginResponseDto login(String email, String password) {
        log.info("Login attempt for email={}", email);

        User user = userDao.findByEmail(email)
                .orElseThrow(() -> {
                    log.warn("Login failed: user not found for email={}", email);
                    return new UserNotFoundException("Invalid email or password");
                });

        if (!passwordService.verify(password, user.getPasswordHash())) {
            log.warn("Login failed: invalid password for email={}", email);
            throw new IllegalArgumentException("Invalid email or password");
        }

        String token = JwtUtil.generateToken(
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                user.getUserRole().getName()
        );

        log.info("Login successful: userId={}, email={}", user.getId(), user.getEmail());
        return new UserLoginResponseDto(token, user.getId());
    }

    @Transactional(readOnly = true)
    public UserResponseDto getByEmail(String email) {
        log.debug("Fetching user by email={}", email);

        User user = userDao.findByEmail(email)
                .orElseThrow(() -> {
                    log.warn("User not found by email={}", email);
                    return new UserNotFoundException("User not found: " + email);
                });

        log.debug("User found by email={}: id={}", email, user.getId());
        return toResponseDto(user);
    }

    public PasswordRestoringResponse restorePassword(String email) {
        log.info("Password restore requested for email={}", email);
        return null;
    }

    private UserResponseDto toResponseDto(User user) {
        return new UserResponseDto(
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                user.getUserRole().getName()
        );
    }

    @Transactional(readOnly = true)
    public List<UserResponseDto> getAll() {
        log.debug("Fetching all users");
        List<UserResponseDto> result = userDao.findAll().stream()
                .map(this::toResponseDto)
                .toList();
        log.debug("Fetched {} users", result.size());
        return result;
    }

    @Transactional(readOnly = true)
    public List<UserResponseDto> getUsersByPage(int page, int size) {
        log.debug("Fetching users page: page={}, size={}", page, size);
        Pageable pageable = PageRequest.of(page - 1, size);
        List<UserResponseDto> result = userDao.findAll(pageable).stream()
                .map(this::toResponseDto)
                .toList();
        log.debug("Fetched {} users for page={}, size={}", result.size(), page, size);
        return result;
    }

    @Transactional(readOnly = true)
    public UserResponseDto getById(int id) {
        log.debug("Fetching user by id={}", id);
        User user = userDao.findById(id)
                .orElseThrow(() -> {
                    log.warn("User not found by id={}", id);
                    return new UserNotFoundException("no such user");
                });
        log.debug("User found by id={}", id);
        return toResponseDto(user);
    }

    @Transactional
    public void updateUser(User updatedUser) {
        log.info("Updating user entity by id={}", updatedUser.getId());

        userDao.findById(updatedUser.getId())
                .orElseThrow(() -> {
                    log.warn("Update failed: user not found id={}", updatedUser.getId());
                    return new UserNotFoundException("no user with such id");
                });

        userDao.save(updatedUser);
        log.info("User entity updated successfully: id={}", updatedUser.getId());
    }

    @Transactional
    public void deleteUser(UserDeleteRequestDto userToDelete) {
        log.info("Deleting user by id={}", userToDelete.getId());

        userDao.findById(userToDelete.getId())
                .orElseThrow(() -> {
                    log.warn("Delete failed: user not found id={}", userToDelete.getId());
                    return new UserNotFoundException("no user with such id");
                });

        userDao.deleteById(userToDelete.getId());
        log.info("User deleted successfully: id={}", userToDelete.getId());
    }

    @Transactional
    public long deleteByFilter(UserDeleteRequestDto userDto) {
        log.info("Deleting users by filter: email={}, username={}, role={}",
                userDto.getEmail(), userDto.getUsername(), userDto.getRole());

        Specification<User> spec = Specification
                .where(UserSpecification.hasEmail(userDto.getEmail()))
                .and(UserSpecification.hasUsername(userDto.getUsername()))
                .and(userDto.getRole() == null ? null :
                        UserSpecification.hasRole(
                                roleRepository.findByName(userDto.getRole())
                                .orElseThrow(() -> {
                                    log.warn("Delete by filter failed: role not found role={}", userDto.getRole());
                                    return new IllegalArgumentException("Role not found: " + userDto.getRole());
                                })
                        ));

        List<User> users = userDao.findAll(spec);
        long count = users.size();
        userDao.deleteAll(users);

        log.info("Delete by filter completed: deleted {} users", count);
        return count;
    }

    @Transactional(readOnly = true)
    public List<UserResponseDto> searchByFilter(UserSerchRequestDto filter) {
        log.debug("Searching users by filter: email={}, username={}, role={}",
                filter.getEmail(), filter.getUsername(), filter.getRole());

        Specification<User> spec = Specification.where((Specification<User>) null);

        if (filter.getEmail() != null && !filter.getEmail().isBlank()) {
            spec = spec.and(UserSpecification.hasEmail(filter.getEmail()));
        }

        if (filter.getUsername() != null && !filter.getUsername().isBlank()) {
            spec = spec.and(UserSpecification.hasUsername(filter.getUsername()));
        }

        if (filter.getRole() != null && !filter.getRole().isBlank()) {
            Role role = roleRepository.findByName(filter.getRole())
                    .orElseThrow(() -> {
                        log.warn("Search failed: role not found role={}", filter.getRole());
                        return new IllegalArgumentException("Role not found: " + filter.getRole());
                    });
            spec = spec.and(UserSpecification.hasRole(role));
        }

        List<UserResponseDto> result = userDao.findAll(spec)
                .stream()
                .map(this::toResponseDto)
                .toList();

        log.debug("Search completed: found {} users", result.size());
        return result;
    }

    @Transactional(readOnly = true)
    public List<UserResponseDto> searchByFilter(UserSerchRequestDto filter, int page, int size) {
        log.debug("Searching users by filter with page: email={}, username={}, role={}, page={}, size={}",
                filter.getEmail(), filter.getUsername(), filter.getRole(), page, size);

        if (page < 1) {
            log.warn("Invalid page value: {}", page);
            throw new IllegalArgumentException("Page must be >= 1");
        }
        if (size < 1) {
            log.warn("Invalid size value: {}", size);
            throw new IllegalArgumentException("Size must be >= 1");
        }

        Specification<User> spec = Specification.where((Specification<User>) null);

        if (filter.getEmail() != null && !filter.getEmail().isBlank()) {
            spec = spec.and(UserSpecification.hasEmail(filter.getEmail()));
        }

        if (filter.getUsername() != null && !filter.getUsername().isBlank()) {
            spec = spec.and(UserSpecification.hasUsername(filter.getUsername()));
        }

        if (filter.getRole() != null && !filter.getRole().isBlank()) {
            Role role = roleRepository.findByName(filter.getRole())
                    .orElseThrow(() -> {
                        log.warn("Paged search failed: role not found role={}", filter.getRole());
                        return new IllegalArgumentException("Role not found: " + filter.getRole());
                    });
            spec = spec.and(UserSpecification.hasRole(role));
        }

        Pageable pageable = PageRequest.of(page - 1, size);

        List<UserResponseDto> result = userDao.findAll(spec, pageable)
                .stream()
                .map(this::toResponseDto)
                .toList();

        log.debug("Paged search completed: found {} users", result.size());
        return result;
    }

    @Transactional
    public UserResponseDto updateUserById(UserUpdateRequestDto request) {
        log.info("Updating user by request: id={}", request.getId());

        if (request.getId() < 0) {
            log.warn("Update failed: invalid user id={}", request.getId());
            throw new IllegalArgumentException("User id must be positive");
        }

        User user = userDao.findById(request.getId())
                .orElseThrow(() -> {
                    log.warn("Update failed: user not found id={}", request.getId());
                    return new UserNotFoundException("No user with id=" + request.getId());
                });

        var builder = User.builder()
                .id(user.getId());

        if (request.getEmail() != null && !request.getEmail().isBlank()) {
            userDao.findByEmail(request.getEmail())
                    .filter(existing -> existing.getId() != user.getId())
                    .ifPresent(existing -> {
                        log.warn("Update failed: email already in use email={}", request.getEmail());
                        throw new IllegalArgumentException("Email already in use: " + request.getEmail());
                    });
            builder.email(request.getEmail());
        } else {
            builder.email(user.getEmail());
        }

        if (request.getUsername() != null && !request.getUsername().isBlank()) {
            builder.username(request.getUsername());
        } else {
            builder.username(user.getUsername());
        }

        if (request.getRole() != null && !request.getRole().isBlank()) {
            Role role = roleRepository.findByName(request.getRole())
                    .orElseThrow(() -> {
                        log.warn("Update failed: role not found role={}", request.getRole());
                        return new IllegalArgumentException("Role not found: " + request.getRole());
                    });
            builder.userRole(role);
        } else {
            builder.userRole(user.getUserRole());
        }

        if (request.getPassword() != null && !request.getPassword().isBlank()) {
            log.debug("Updating password for user id={}", request.getId());
            builder.passwordHash(passwordService.hash(request.getPassword()));
        } else {
            builder.passwordHash(user.getPasswordHash());
        }

        User saved = userDao.save(builder.build());
        log.info("User updated successfully: id={}", saved.getId());

        return toResponseDto(saved);
    }
}