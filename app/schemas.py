from pydantic import BaseModel


class ExperienceItem(BaseModel):
    title: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class EducationItem(BaseModel):
    school: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class CertificationItem(BaseModel):
    name: str | None = None
    issuer: str | None = None
    issue_date: str | None = None


class ProfileResponse(BaseModel):
    linkedin_sub: str | None = None
    name: str | None = None
    headline: str | None = None
    location: str | None = None
    about: str | None = None
    email: str | None = None
    profile_image_url: str | None = None

    experience: list[ExperienceItem] = []
    education: list[EducationItem] = []
    skills: list[str] = []
    certifications: list[CertificationItem] = []
    languages: list[str] = []

    data_source: str = "linkedin_oauth"
    fields_unavailable: list[str] = []
