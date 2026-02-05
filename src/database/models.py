"""SQLAlchemy database models."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text,
    DECIMAL, ARRAY, ForeignKey, JSON, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Contract(Base):
    """Polymarket contract model."""

    __tablename__ = 'contracts'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    contract_id = Column(String(255), unique=True, nullable=False, index=True)
    question = Column(Text, nullable=False)
    description = Column(Text)
    end_date = Column(DateTime)
    category = Column(String(100), index=True)
    current_yes_odds = Column(DECIMAL(5, 4))
    current_no_odds = Column(DECIMAL(5, 4))
    volume_24h = Column(DECIMAL(15, 2))
    liquidity = Column(DECIMAL(15, 2))
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    historical_odds = relationship("HistoricalOdds", back_populates="contract", cascade="all, delete-orphan")
    sentiment_analyses = relationship("SentimentAnalysis", back_populates="contract", cascade="all, delete-orphan")
    detected_gaps = relationship("DetectedGap", back_populates="contract", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Contract(id='{self.contract_id}', question='{self.question[:50]}...')>"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'contract_id': self.contract_id,
            'question': self.question,
            'description': self.description,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'category': self.category,
            'current_yes_odds': float(self.current_yes_odds) if self.current_yes_odds else None,
            'current_no_odds': float(self.current_no_odds) if self.current_no_odds else None,
            'volume_24h': float(self.volume_24h) if self.volume_24h else None,
            'liquidity': float(self.liquidity) if self.liquidity else None,
            'active': self.active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class HistoricalOdds(Base):
    """Historical odds tracking model."""

    __tablename__ = 'historical_odds'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    contract_id = Column(UUID(as_uuid=True), ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False)
    yes_odds = Column(DECIMAL(5, 4), nullable=False)
    no_odds = Column(DECIMAL(5, 4), nullable=False)
    volume = Column(DECIMAL(15, 2))
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    contract = relationship("Contract", back_populates="historical_odds")

    def __repr__(self):
        return f"<HistoricalOdds(contract_id='{self.contract_id}', yes={self.yes_odds})>"


class SocialPost(Base):
    """Social media post model."""

    __tablename__ = 'social_posts'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    post_id = Column(String(255), unique=True, nullable=False)
    platform = Column(String(50), nullable=False, index=True)  # 'twitter', 'reddit'
    author = Column(String(255))
    content = Column(Text, nullable=False)
    url = Column(Text)
    engagement_score = Column(Integer, default=0)
    posted_at = Column(DateTime, nullable=False, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    related_contracts = Column(ARRAY(UUID(as_uuid=True)), index=True)

    # Relationships
    sentiment_analyses = relationship("SentimentAnalysis", back_populates="post", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SocialPost(platform='{self.platform}', author='{self.author}')>"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'post_id': self.post_id,
            'platform': self.platform,
            'author': self.author,
            'content': self.content,
            'url': self.url,
            'engagement_score': self.engagement_score,
            'posted_at': self.posted_at.isoformat(),
            'fetched_at': self.fetched_at.isoformat(),
            'related_contracts': [str(c) for c in self.related_contracts] if self.related_contracts else []
        }


class SentimentAnalysis(Base):
    """Sentiment analysis results model."""

    __tablename__ = 'sentiment_analysis'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    post_id = Column(UUID(as_uuid=True), ForeignKey('social_posts.id', ondelete='CASCADE'))
    contract_id = Column(UUID(as_uuid=True), ForeignKey('contracts.id', ondelete='CASCADE'), index=True)
    sentiment_score = Column(DECIMAL(4, 3))  # -1.0 to 1.0
    sentiment_label = Column(String(20))  # 'positive', 'negative', 'neutral'
    confidence = Column(DECIMAL(4, 3))  # 0.0 to 1.0
    topics = Column(ARRAY(String))
    analyzed_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    post = relationship("SocialPost", back_populates="sentiment_analyses")
    contract = relationship("Contract", back_populates="sentiment_analyses")

    def __repr__(self):
        return f"<SentimentAnalysis(label='{self.sentiment_label}', score={self.sentiment_score})>"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'post_id': str(self.post_id) if self.post_id else None,
            'contract_id': str(self.contract_id) if self.contract_id else None,
            'sentiment_score': float(self.sentiment_score) if self.sentiment_score else None,
            'sentiment_label': self.sentiment_label,
            'confidence': float(self.confidence) if self.confidence else None,
            'topics': self.topics,
            'analyzed_at': self.analyzed_at.isoformat()
        }


class DetectedGap(Base):
    """Detected pricing gap model."""

    __tablename__ = 'detected_gaps'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    contract_id = Column(UUID(as_uuid=True), ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False, index=True)
    gap_type = Column(String(50), nullable=False)  # 'sentiment_mismatch', 'info_asymmetry', 'arbitrage', 'pattern_deviation'
    confidence_score = Column(
        Integer,
        CheckConstraint('confidence_score >= 0 AND confidence_score <= 100'),
        nullable=False,
        index=True
    )
    explanation = Column(Text, nullable=False)
    evidence = Column(JSONB)  # Structured evidence data
    market_odds = Column(DECIMAL(5, 4))
    implied_odds = Column(DECIMAL(5, 4))  # What odds should be
    edge_percentage = Column(DECIMAL(5, 2))
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime)

    # Relationships
    contract = relationship("Contract", back_populates="detected_gaps")

    def __repr__(self):
        return f"<DetectedGap(type='{self.gap_type}', confidence={self.confidence_score})>"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'contract_id': str(self.contract_id),
            'gap_type': self.gap_type,
            'confidence_score': self.confidence_score,
            'explanation': self.explanation,
            'evidence': self.evidence,
            'market_odds': float(self.market_odds) if self.market_odds else None,
            'implied_odds': float(self.implied_odds) if self.implied_odds else None,
            'edge_percentage': float(self.edge_percentage) if self.edge_percentage else None,
            'detected_at': self.detected_at.isoformat(),
            'resolved': self.resolved,
            'resolution_notes': self.resolution_notes,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


class SystemLog(Base):
    """System logging model."""

    __tablename__ = 'system_logs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    log_level = Column(String(20), nullable=False, index=True)  # 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    agent_name = Column(String(100))
    message = Column(Text, nullable=False)
    log_metadata = Column(JSONB)  # Renamed from 'metadata' to avoid SQLAlchemy conflict
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<SystemLog(level='{self.log_level}', agent='{self.agent_name}')>"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'log_level': self.log_level,
            'agent_name': self.agent_name,
            'message': self.message,
            'log_metadata': self.log_metadata,
            'created_at': self.created_at.isoformat()
        }
