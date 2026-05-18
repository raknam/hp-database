from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint, func, JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    slug: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(20))
    name_ja: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    name_en: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    name_kana: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_artist_source_ext"),
    )

    releases: Mapped[list[Release]] = relationship("Release", back_populates="artist")
    parent_relations: Mapped[list[ArtistRelation]] = relationship(
        "ArtistRelation", foreign_keys="[ArtistRelation.parent_id]", back_populates="parent"
    )
    child_relations: Mapped[list[ArtistRelation]] = relationship(
        "ArtistRelation", foreign_keys="[ArtistRelation.child_id]", back_populates="child"
    )


class ArtistRelation(Base):
    __tablename__ = "artist_relations"

    parent_id: Mapped[int] = mapped_column(Integer, ForeignKey("artists.id"), primary_key=True)
    child_id: Mapped[int] = mapped_column(Integer, ForeignKey("artists.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    joined_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    left_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    parent: Mapped[Artist] = relationship("Artist", foreign_keys=[parent_id], back_populates="parent_relations")
    child: Mapped[Artist] = relationship("Artist", foreign_keys=[child_id], back_populates="child_relations")


class Release(Base):
    __tablename__ = "releases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    release_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    release_format: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    artist_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("artists.id"), nullable=True)
    artist_label_raw: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    release_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_release_source_ext"),
    )

    artist: Mapped[Optional[Artist]] = relationship("Artist", back_populates="releases")
    images: Mapped[list[ReleaseImage]] = relationship(
        "ReleaseImage", back_populates="release",
        order_by="ReleaseImage.sort_order", cascade="all, delete-orphan"
    )
    editions: Mapped[list[Edition]] = relationship(
        "Edition", back_populates="release",
        order_by="Edition.sort_order", cascade="all, delete-orphan"
    )
    group_member: Mapped[Optional[ReleaseGroupMember]] = relationship(
        "ReleaseGroupMember", back_populates="release", uselist=False
    )


class ReleaseImage(Base):
    __tablename__ = "release_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    release_id: Mapped[int] = mapped_column(Integer, ForeignKey("releases.id"))
    path: Mapped[str] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    release: Mapped[Release] = relationship("Release", back_populates="images")


class Edition(Base):
    __tablename__ = "editions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    release_id: Mapped[int] = mapped_column(Integer, ForeignKey("releases.id"))
    name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    price_raw: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    price_jpy: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    release: Mapped[Release] = relationship("Release", back_populates="editions")
    discs: Mapped[list[Disc]] = relationship(
        "Disc", back_populates="edition",
        order_by="Disc.sort_order", cascade="all, delete-orphan"
    )
    collection_item: Mapped[Optional[CollectionItem]] = relationship(
        "CollectionItem", back_populates="edition", uselist=False
    )


class Disc(Base):
    __tablename__ = "discs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    edition_id: Mapped[int] = mapped_column(Integer, ForeignKey("editions.id"))
    disc_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    catalog_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    jan: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    edition: Mapped[Edition] = relationship("Edition", back_populates="discs")
    tracks: Mapped[list[Track]] = relationship(
        "Track", back_populates="disc",
        order_by="Track.index_no", cascade="all, delete-orphan"
    )
    iso_files: Mapped[list[IsoFile]] = relationship("IsoFile", back_populates="disc")


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    disc_id: Mapped[int] = mapped_column(Integer, ForeignKey("discs.id"))
    index_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    suffix: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    song_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("songs.id"), nullable=True)

    disc: Mapped[Disc] = relationship("Disc", back_populates="tracks")
    song: Mapped[Optional[Song]] = relationship("Song", back_populates="tracks")
    credits: Mapped[list[TrackCredit]] = relationship(
        "TrackCredit", back_populates="track", cascade="all, delete-orphan"
    )


class TrackCredit(Base):
    __tablename__ = "track_credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track_id: Mapped[int] = mapped_column(Integer, ForeignKey("tracks.id"))
    role: Mapped[str] = mapped_column(String(100))
    credit_text: Mapped[str] = mapped_column(Text)
    artist_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("artists.id"), nullable=True)

    track: Mapped[Track] = relationship("Track", back_populates="credits")


class Song(Base):
    __tablename__ = "songs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title_canonical: Mapped[str] = mapped_column(String(500))
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tracks: Mapped[list[Track]] = relationship("Track", back_populates="song")
    video_clips: Mapped[list[VideoClip]] = relationship("VideoClip", back_populates="song")


class VideoClip(Base):
    __tablename__ = "video_clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    song_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("songs.id"), nullable=True)
    track_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tracks.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(200))
    kind: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    song: Mapped[Optional[Song]] = relationship("Song", back_populates="video_clips")


class CollectionItem(Base):
    __tablename__ = "collection_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    edition_id: Mapped[int] = mapped_column(Integer, ForeignKey("editions.id"), unique=True)
    owned: Mapped[bool] = mapped_column(Boolean, default=False)
    condition: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    acquired_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    acquired_price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    acquired_from: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    edition: Mapped[Edition] = relationship("Edition", back_populates="collection_item")


class IsoFile(Base):
    __tablename__ = "iso_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    disc_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("discs.id"), nullable=True)
    nas_path: Mapped[str] = mapped_column(String(1000), unique=True)
    relative_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    format: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    present: Mapped[bool] = mapped_column(Boolean, default=True)

    disc: Mapped[Optional[Disc]] = relationship("Disc", back_populates="iso_files")


class ReleaseGroup(Base):
    __tablename__ = "release_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title_override: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    members: Mapped[list[ReleaseGroupMember]] = relationship(
        "ReleaseGroupMember", back_populates="group", cascade="all, delete-orphan"
    )


class ReleaseGroupMember(Base):
    __tablename__ = "release_group_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("release_groups.id"))
    release_id: Mapped[int] = mapped_column(Integer, ForeignKey("releases.id"), unique=True)
    format_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    group: Mapped[ReleaseGroup] = relationship("ReleaseGroup", back_populates="members")
    release: Mapped[Release] = relationship("Release", back_populates="group_member")


class ReleaseGroupDismissal(Base):
    __tablename__ = "release_group_dismissals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    release_ids_key: Mapped[str] = mapped_column(String(500), unique=True)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
