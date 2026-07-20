"""
Social media integrations — one small class per platform, since each has a
different auth flow and API shape. All implement BaseIntegration so the
`automation` and future `social_media` plugins can post/read without
caring which platform they're talking to.

STATUS: stubs. Fill in exchange_code_for_token / post methods per platform
docs as each is connected:
  - Twitter/X: https://developer.twitter.com/en/docs/authentication/oauth-2-0
  - LinkedIn:  https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
  - Facebook & Instagram (Graph API): https://developers.facebook.com/docs/facebook-login
"""
from app.config import settings
from app.exceptions import IntegrationError
from app.integrations.base import BaseIntegration, IntegrationActionResult


class TwitterIntegration(BaseIntegration):
    name = "twitter"
    description = "Post and read on X/Twitter."

    async def is_connected(self) -> bool:
        return bool(settings.TWITTER_API_KEY and settings.TWITTER_API_SECRET)

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        if not settings.TWITTER_API_KEY:
            raise IntegrationError("TWITTER_API_KEY is not configured")
        return (
            "https://twitter.com/i/oauth2/authorize"
            f"?client_id={settings.TWITTER_API_KEY}&redirect_uri={redirect_uri}"
            f"&response_type=code&scope=tweet.read%20tweet.write%20users.read"
            f"&state={state}&code_challenge=challenge&code_challenge_method=plain"
        )

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        raise NotImplementedError("Twitter token exchange not yet implemented")

    async def post_tweet(self, text: str) -> IntegrationActionResult:
        raise NotImplementedError("post_tweet not yet implemented")


class LinkedInIntegration(BaseIntegration):
    name = "linkedin"
    description = "Post and read on LinkedIn."

    async def is_connected(self) -> bool:
        return bool(settings.LINKEDIN_ACCESS_TOKEN)

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        raise NotImplementedError("LinkedIn OAuth URL builder not yet implemented")

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        raise NotImplementedError("LinkedIn token exchange not yet implemented")

    async def post_update(self, text: str) -> IntegrationActionResult:
        raise NotImplementedError("post_update not yet implemented")


class FacebookIntegration(BaseIntegration):
    name = "facebook"
    description = "Post and read on Facebook Pages."

    async def is_connected(self) -> bool:
        return bool(settings.FACEBOOK_ACCESS_TOKEN)

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        raise NotImplementedError("Facebook OAuth URL builder not yet implemented")

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        raise NotImplementedError("Facebook token exchange not yet implemented")

    async def post_update(self, message: str) -> IntegrationActionResult:
        raise NotImplementedError("post_update not yet implemented")


class InstagramIntegration(BaseIntegration):
    name = "instagram"
    description = "Post to Instagram (via the Facebook Graph API)."

    async def is_connected(self) -> bool:
        return bool(settings.INSTAGRAM_ACCESS_TOKEN)

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        raise NotImplementedError("Instagram OAuth URL builder not yet implemented")

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        raise NotImplementedError("Instagram token exchange not yet implemented")

    async def post_image(self, image_url: str, caption: str) -> IntegrationActionResult:
        raise NotImplementedError("post_image not yet implemented")
