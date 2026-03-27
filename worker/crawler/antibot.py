"""Advanced anti-bot detection evasion for web crawling."""
import random
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger(__name__)

# Realistic User-Agent strings from real browsers (updated regularly)
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# Accept-Language variations for Norwegian users
ACCEPT_LANGUAGES = [
    "nb-NO,nb;q=0.9,no;q=0.8,en-US;q=0.7,en;q=0.6",
    "nb-NO,nb;q=0.9,en-US;q=0.8,en;q=0.7",
    "no-NO,no;q=0.9,nb;q=0.8,en-US;q=0.7,en;q=0.6",
    "nb,no;q=0.9,en;q=0.8",
    "nb-NO,nb;q=0.9,no;q=0.8,nn;q=0.7,en-US;q=0.6,en;q=0.5",
]

# Screen resolutions for viewport randomization
SCREEN_RESOLUTIONS = [
    (1920, 1080),
    (1366, 768),
    (1536, 864),
    (1440, 900),
    (1280, 720),
    (1600, 900),
    (2560, 1440),
    (1680, 1050),
]

# Timezone offsets (in minutes) for Norwegian users
TIMEZONE_OFFSETS = [60, 120]  # CET and CEST


@dataclass
class DomainState:
    """Track state for a specific domain to manage anti-bot behavior."""
    consecutive_errors: int = 0
    last_error_time: Optional[datetime] = None
    last_request_time: Optional[datetime] = None
    total_requests: int = 0
    blocked_count: int = 0
    current_delay: float = 2.0
    user_agent_index: int = 0
    session_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def reset_session(self):
        """Reset session state (simulates new browser session)."""
        self.user_agent_index = random.randint(0, len(USER_AGENTS) - 1)
        self.session_start = datetime.now(timezone.utc)
        self.consecutive_errors = 0


class AntiBotManager:
    """Manages anti-bot detection evasion strategies."""
    
    def __init__(self):
        self._domain_states: Dict[str, DomainState] = {}
        self._global_request_count = 0
        self._session_fingerprint = self._generate_fingerprint()
    
    def _get_domain_state(self, domain: str) -> DomainState:
        """Get or create domain state."""
        if domain not in self._domain_states:
            self._domain_states[domain] = DomainState(
                user_agent_index=random.randint(0, len(USER_AGENTS) - 1)
            )
        return self._domain_states[domain]
    
    def _generate_fingerprint(self) -> Dict:
        """Generate a consistent browser fingerprint for the session."""
        resolution = random.choice(SCREEN_RESOLUTIONS)
        return {
            "screen_width": resolution[0],
            "screen_height": resolution[1],
            "color_depth": random.choice([24, 32]),
            "timezone_offset": random.choice(TIMEZONE_OFFSETS),
            "language": random.choice(["nb-NO", "no-NO", "nb"]),
            "platform": random.choice(["Win32", "MacIntel"]),
            "hardware_concurrency": random.choice([4, 8, 12, 16]),
            "device_memory": random.choice([4, 8, 16, 32]),
        }
    
    def get_headers(self, domain: str, url: str) -> Dict[str, str]:
        """Get randomized but consistent headers for a request."""
        state = self._get_domain_state(domain)
        user_agent = USER_AGENTS[state.user_agent_index]
        accept_language = random.choice(ACCEPT_LANGUAGES)
        
        # Determine browser type from user agent
        is_firefox = "Firefox" in user_agent
        is_safari = "Safari" in user_agent and "Chrome" not in user_agent
        is_edge = "Edg/" in user_agent
        
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": accept_language,
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        # Add browser-specific headers
        if not is_firefox and not is_safari:
            # Chrome/Edge specific headers
            chrome_version = "120" if "120" in user_agent else "119" if "119" in user_agent else "121"
            headers.update({
                "Sec-Ch-Ua": f'"Not_A Brand";v="8", "Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"' if "Windows" in user_agent else '"macOS"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            })
        
        # Occasionally add cache control headers (like a real browser refresh)
        if random.random() < 0.1:
            headers["Cache-Control"] = "no-cache"
            headers["Pragma"] = "no-cache"
        
        # Add DNT header randomly (some users have it enabled)
        if random.random() < 0.3:
            headers["DNT"] = "1"
        
        return headers
    
    def get_browser_context_options(self, domain: str) -> Dict:
        """Get options for Playwright browser context."""
        state = self._get_domain_state(domain)
        user_agent = USER_AGENTS[state.user_agent_index]
        fp = self._session_fingerprint
        
        # Add slight randomization to viewport
        width = fp["screen_width"] + random.randint(-50, 50)
        height = fp["screen_height"] + random.randint(-50, 50)
        
        return {
            "user_agent": user_agent,
            "viewport": {"width": width, "height": height},
            "locale": fp["language"],
            "timezone_id": "Europe/Oslo",
            "color_scheme": random.choice(["light", "dark", "no-preference"]),
            "reduced_motion": random.choice(["reduce", "no-preference"]),
            "has_touch": False,
            "is_mobile": False,
            "device_scale_factor": random.choice([1, 1.25, 1.5, 2]),
            "extra_http_headers": {
                "Accept-Language": random.choice(ACCEPT_LANGUAGES),
            },
        }
    
    async def get_delay(self, domain: str) -> float:
        """Calculate appropriate delay based on domain state."""
        state = self._get_domain_state(domain)
        
        # Base delay with exponential backoff on errors
        base_delay = state.current_delay
        
        # Add randomization (human-like variance)
        jitter = random.uniform(0.5, 2.0)
        delay = base_delay * jitter
        
        # Add extra delay if we've had recent errors
        if state.consecutive_errors > 0:
            error_multiplier = min(2 ** state.consecutive_errors, 16)  # Cap at 16x
            delay *= error_multiplier
            logger.info("Applying error backoff", domain=domain, multiplier=error_multiplier, delay=round(delay, 2))
        
        # Occasionally add longer "thinking" pauses (simulates user reading)
        if random.random() < 0.1:
            delay += random.uniform(3, 8)
        
        # Cap maximum delay at 60 seconds
        return min(delay, 60.0)
    
    def record_success(self, domain: str):
        """Record a successful request."""
        state = self._get_domain_state(domain)
        state.consecutive_errors = 0
        state.total_requests += 1
        state.last_request_time = datetime.now(timezone.utc)
        
        # Gradually reduce delay on success (but not below minimum)
        state.current_delay = max(2.0, state.current_delay * 0.95)
        
        self._global_request_count += 1
    
    def record_error(self, domain: str, status_code: Optional[int] = None, is_blocked: bool = False):
        """Record a failed request and adjust strategy."""
        state = self._get_domain_state(domain)
        state.consecutive_errors += 1
        state.last_error_time = datetime.now(timezone.utc)
        
        if is_blocked or status_code in (403, 429, 503):
            state.blocked_count += 1
            # Increase delay significantly on block
            state.current_delay = min(state.current_delay * 2, 30.0)
            
            # Rotate user agent on block
            state.user_agent_index = (state.user_agent_index + 1) % len(USER_AGENTS)
            
            logger.warning("Blocked detected, rotating user agent", 
                domain=domain, 
                new_ua_index=state.user_agent_index,
                new_delay=state.current_delay,
                blocked_count=state.blocked_count
            )
            
            # If blocked too many times, reset session
            if state.blocked_count >= 3:
                state.reset_session()
                state.current_delay = 10.0  # Start with higher delay after reset
                logger.warning("Too many blocks, resetting session", domain=domain)
        else:
            # Regular error, moderate delay increase
            state.current_delay = min(state.current_delay * 1.5, 20.0)
    
    def should_skip_domain(self, domain: str) -> Tuple[bool, Optional[str]]:
        """Check if we should temporarily skip this domain."""
        state = self._get_domain_state(domain)
        
        # Skip if too many consecutive errors
        if state.consecutive_errors >= 5:
            return True, f"Too many consecutive errors ({state.consecutive_errors})"
        
        # Skip if blocked too many times recently
        if state.blocked_count >= 5:
            if state.last_error_time:
                time_since_block = datetime.now(timezone.utc) - state.last_error_time
                if time_since_block < timedelta(hours=1):
                    return True, f"Domain blocked, waiting for cooldown ({state.blocked_count} blocks)"
        
        return False, None
    
    def get_human_scroll_pattern(self) -> List[Dict]:
        """Generate a human-like scroll pattern for browser automation."""
        patterns = []
        current_y = 0
        page_height = random.randint(3000, 8000)
        
        while current_y < page_height:
            # Variable scroll distance
            scroll_distance = random.randint(200, 600)
            current_y += scroll_distance
            
            # Variable pause duration
            pause = random.uniform(0.1, 0.5)
            
            # Occasionally pause longer (reading)
            if random.random() < 0.15:
                pause += random.uniform(1, 3)
            
            # Occasionally scroll back up slightly
            if random.random() < 0.1 and current_y > 500:
                patterns.append({
                    "y": current_y - random.randint(100, 300),
                    "pause": random.uniform(0.2, 0.5),
                })
            
            patterns.append({
                "y": min(current_y, page_height),
                "pause": pause,
            })
        
        return patterns
    
    def get_mouse_movement_pattern(self) -> List[Dict]:
        """Generate human-like mouse movement coordinates."""
        movements = []
        x, y = random.randint(100, 500), random.randint(100, 300)
        
        for _ in range(random.randint(3, 8)):
            # Move to random position with some variance
            target_x = x + random.randint(-200, 200)
            target_y = y + random.randint(-150, 150)
            
            # Ensure within reasonable bounds
            target_x = max(50, min(target_x, 1800))
            target_y = max(50, min(target_y, 900))
            
            movements.append({
                "x": target_x,
                "y": target_y,
                "duration": random.uniform(0.1, 0.4),
            })
            
            x, y = target_x, target_y
        
        return movements


# Global instance
antibot_manager = AntiBotManager()


def get_random_user_agent() -> str:
    """Get a random user agent string."""
    return random.choice(USER_AGENTS)


def get_random_headers(domain: str, url: str) -> Dict[str, str]:
    """Get randomized headers for a request."""
    return antibot_manager.get_headers(domain, url)


async def get_adaptive_delay(domain: str) -> float:
    """Get adaptive delay based on domain history."""
    return await antibot_manager.get_delay(domain)


def record_request_result(domain: str, success: bool, status_code: Optional[int] = None, is_blocked: bool = False):
    """Record the result of a request for adaptive behavior."""
    if success:
        antibot_manager.record_success(domain)
    else:
        antibot_manager.record_error(domain, status_code, is_blocked)
