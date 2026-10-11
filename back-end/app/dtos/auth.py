from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=255)
    password: str = Field(max_length=1024)
    confirm_password: str = Field(max_length=1024)


class ConfirmRegistrationRequest(BaseModel):
    registration_id: str = Field(min_length=32, max_length=32)
    code: str = Field(pattern=r"^\d{3}$")


class ResendRequest(BaseModel):
    registration_id: str = Field(min_length=32, max_length=32)


class LoginRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=1024)


class EmailRequest(BaseModel):
    email: str = Field(max_length=255)


class ResetTokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=200)


class ResetPasswordRequest(ResetTokenRequest):
    password: str = Field(max_length=1024)
    confirm_password: str = Field(max_length=1024)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=1024)
    password: str = Field(max_length=1024)
    confirm_password: str = Field(max_length=1024)


class ProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class UserProfileDTO(BaseModel):
    id: str
    first_name: str
    role: str


class PasswordRecoveryDTO(BaseModel):
    masked_email: str
