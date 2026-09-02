"""
Identity System
Authentication and permission management
"""
from typing import Set, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import uuid
from enum import Enum


class Permission(str, Enum):
    """Basic permissions"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    GOVERN = "govern"
    VERIFY = "verify"
    AUDIT = "audit"
    ADMIN = "admin"


@dataclass
class Identity:
    """Represents an actor in the system"""
    id: str
    name: str
    actor_type: str  # user, service, system
    permissions: Set[Permission] = field(default_factory=set)
    capabilities: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    active: bool = True
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if identity has permission"""
        return permission in self.permissions or Permission.ADMIN in self.permissions
    
    def has_capability(self, capability: str) -> bool:
        """Check if identity has capability"""
        return capability in self.capabilities
    
    def grant_permission(self, permission: Permission) -> None:
        """Grant a permission"""
        self.permissions.add(permission)
    
    def revoke_permission(self, permission: Permission) -> None:
        """Revoke a permission"""
        self.permissions.discard(permission)
    
    def grant_capability(self, capability: str) -> None:
        """Grant a capability"""
        self.capabilities.add(capability)
    
    def revoke_capability(self, capability: str) -> None:
        """Revoke a capability"""
        self.capabilities.discard(capability)
    
    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_activity = datetime.now()


@dataclass
class Session:
    """Represents an authenticated session"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    identity_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=1))
    active: bool = True
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        return datetime.now() > self.expires_at
    
    def extend(self, hours: int = 1) -> None:
        """Extend session expiration"""
        self.expires_at = datetime.now() + timedelta(hours=hours)


class IdentityService:
    """Manages identities and sessions"""
    
    def __init__(self):
        self.identities: dict[str, Identity] = {}
        self.sessions: dict[str, Session] = {}
    
    def create_identity(
        self,
        name: str,
        actor_type: str,
        permissions: Optional[Set[Permission]] = None,
    ) -> Identity:
        """Create new identity"""
        identity_id = str(uuid.uuid4())
        identity = Identity(
            id=identity_id,
            name=name,
            actor_type=actor_type,
            permissions=permissions or set(),
        )
        self.identities[identity_id] = identity
        return identity
    
    def get_identity(self, identity_id: str) -> Optional[Identity]:
        """Get identity by ID"""
        return self.identities.get(identity_id)
    
    def authenticate(self, identity_id: str) -> Optional[Session]:
        """Authenticate identity and create session"""
        identity = self.get_identity(identity_id)
        if not identity or not identity.active:
            return None
        
        session = Session(identity_id=identity_id)
        self.sessions[session.session_id] = session
        identity.update_activity()
        return session
    
    def verify_session(self, session_id: str) -> bool:
        """Verify session is valid"""
        session = self.sessions.get(session_id)
        if not session:
            return False
        if session.is_expired():
            session.active = False
            return False
        return session.active
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session details"""
        if self.verify_session(session_id):
            return self.sessions.get(session_id)
        return None
    
    def revoke_session(self, session_id: str) -> None:
        """Revoke a session"""
        if session_id in self.sessions:
            self.sessions[session_id].active = False
