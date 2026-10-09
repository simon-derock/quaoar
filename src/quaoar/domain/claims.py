# claims as printed in a prospectus; each one carries its page and the exact words it came from
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

# pdf line breaks cut names mid-word-group; every printed name is one clean line
Tidy = Annotated[str, AfterValidator(lambda text: " ".join(text.split()))]


class Grounded(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: int = Field(ge=1, description="pdf page number from the [[page N]] marker")
    # the stored span is cut from the page by code; whatever the model writes here is ignored
    span: str = Field(default="", max_length=4000, description="optional short quote")


class QuoteClaim(Grounded):
    vendor: Tidy = Field(description="quotation from, exactly as printed")
    item: Tidy = Field(description="what is being bought")
    amount_text: Tidy = Field(description="amount exactly as printed, digits and commas")
    unit_text: str = Field(default="", description="unit as printed, e.g. Lakhs, Crore, Rs.")
    quote_date_text: str = Field(default="", description="quotation date as printed")


class LeadManagerClaim(Grounded):
    name: Tidy


class PastIssueClaim(Grounded):
    issuer: Tidy
    listing_date_text: str = ""
    issue_price_text: str = ""


class DisclosedCaseClaim(Grounded):
    party: Tidy = Field(description="company or person the case is against or by, as printed")
    forum: Tidy = ""
    case_ref: Tidy = ""
    nature: str = ""


class PlaceClaim(Grounded):
    role: Literal["registered_office", "corporate_office", "factory", "warehouse", "other"]
    locality: Tidy = Field(description="area or industrial estate, never a house or flat number")
    city: Tidy


class PromoterClaim(Grounded):
    name: Tidy


class GroupCompanyClaim(Grounded):
    name: Tidy


class Quotes(BaseModel):
    items: list[QuoteClaim]


class LeadManagers(BaseModel):
    items: list[LeadManagerClaim]


class PastIssues(BaseModel):
    items: list[PastIssueClaim]


class DisclosedCases(BaseModel):
    items: list[DisclosedCaseClaim]


class Places(BaseModel):
    items: list[PlaceClaim]


class Promoters(BaseModel):
    items: list[PromoterClaim]


class GroupCompanies(BaseModel):
    items: list[GroupCompanyClaim]
