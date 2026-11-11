from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from backend.data.database import Base

class Race(Base):
    __tablename__ = "races"
    polls = relationship("Poll", back_populates="candidate")

    race_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    election_year: Mapped[int] = mapped_column(Integer, nullable=False)
    election_date: Mapped[object] = mapped_column(Date, nullable=False)
    seat_class: Mapped[str | None] = mapped_column(String(50))
    election_type: Mapped[str] = mapped_column(String(50), nullable=False)
    incumbent: Mapped[str | None] = mapped_column(String(200))
    incumbent_party: Mapped[str | None] = mapped_column(String(50))
    is_open_seat: Mapped[bool | None] = mapped_column(Boolean)

    candidates = relationship("Candidate", back_populates="race")
    polls = relationship("Poll", back_populates="race")
    
    __table_args__ = (
        UniqueConstraint(
            "state_code",
            "election_year",
            "seat_class",
            "election_type",
            name="unique_race"
        ),
    )


class Candidate(Base):
    __tablename__ = "candidates"
    polls = relationship("Poll", back_populates="candidate")
    race = relationship("Race", back_populates="candidates")

    candidate_id: Mapped[str] = mapped_column(String(250), primary_key=True)
    race_id: Mapped[str] = mapped_column(ForeignKey("races.race_id"), nullable=False)

    candidate_name: Mapped[str] = mapped_column(String(250), nullable=False)
    party: Mapped[str | None] = mapped_column(String(50))
    is_incumbent: Mapped[bool | None] = mapped_column(Boolean)
    ballot_status: Mapped[str | None] = mapped_column(String(50))

##took out contraint




class Poll(Base):
    __tablename__ = "polls"

    id = Column(Integer, primary_key=True)

    poll_id = Column(String(100), nullable=False)
    question_id = Column(String(250), nullable=False)
    race = relationship("Race", back_populates="polls")
    candidate = relationship("Candidate", back_populates="polls")


    race_id = Column(String(150),ForeignKey("races.race_id"),nullable=False)
    candidate_id = Column(String(250),ForeignKey("candidates.candidate_id"),nullable=True)

    candidate_name = Column(String(250), nullable=False)
    poll_election_type = Column(String(20),nullable=False)
    primary_party = Column(String(10), nullable=True) ## added to fix duplication issues 

    pollster = Column(String(250))
    start_date = Column(Date)
    end_date = Column(Date)
    sample_size = Column(Integer)
    population = Column(String(100))
    pct = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "poll_id",
            "question_id",
            "candidate_name",
            name="uq_poll_response"
        ),
        CheckConstraint( ##check vs unique 
            "pct >= 0 AND pct <= 100",
            name="poll_percentage"
        ),
        CheckConstraint(
            "sample_size IS NULL OR (sample_size > 50 AND sample_size <= 100000)",
            name="reasonable_sample_size"
        ),
    )

class HistoricalResult(Base):
    __tablename__ = "historical_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[str] = mapped_column(String(250), nullable=False)
    election_year: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    candidate: Mapped[str] = mapped_column(String(250), nullable=False)
    party: Mapped[str | None] = mapped_column(String(50))
    candidate_votes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_votes: Mapped[int] = mapped_column(Integer, nullable=False)
    dem_margin: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint(
            "race_id", "candidate",
            name="unique_candidate"
        ),
    )



class HistoricalPoll(Base):
    __tablename__ = "historical_polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    poll_id: Mapped[str] = mapped_column(String(100), nullable=False)
    question_id: Mapped[str] = mapped_column(String(250), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(250), nullable=False)

    race_id: Mapped[str | None] = mapped_column(String(100))
    election_year: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    pollster: Mapped[str | None] = mapped_column(String(200))
    end_date: Mapped[object | None] = mapped_column(Date)
    election_date: Mapped[object | None] = mapped_column(Date)
    days_to_election: Mapped[int | None] = mapped_column(Integer)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    population: Mapped[str | None] = mapped_column(String(100))
    party: Mapped[str | None] = mapped_column(String(50))
    pct: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "poll_id", "question_id", "candidate_id",
            name="uq_historical_poll_response"
        ),
        CheckConstraint(
            "pct >= 0 AND pct <= 100",
            name="ck_historical_poll_pct"
        ),
        CheckConstraint(
        "sample_size > 50 AND sample_size <= 100000",
        name="reasonable_sample_size"
        ),
    )



class GenericBallot(Base):
    __tablename__ = "generic_ballot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poll_id: Mapped[str] = mapped_column(String(100), nullable=False)
    question_id: Mapped[str] = mapped_column(String(100), nullable=False)
    pollster: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[object | None] = mapped_column(Date)
    end_date: Mapped[object | None] = mapped_column(Date)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    population: Mapped[str | None] = mapped_column(String(100))
    party: Mapped[str] = mapped_column(String(50), nullable=False)
    pct: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "poll_id", "question_id", "party",
            name="uq_generic_ballot_response"
        ),
        CheckConstraint(
            "pct >= 0 AND pct <= 100",
            name="ck_generic_ballot_pct"
        ),
        CheckConstraint(
        "sample_size > 50 AND sample_size <= 100000",
        name="reasonable_sample_size"
        ),
    )


class HistoricalGenericBallot(Base):
    __tablename__ = "historical_generic_ballot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poll_id: Mapped[str] = mapped_column(String(100), nullable=False)
    question_id: Mapped[str] = mapped_column(String(100), nullable=False)
    election_year: Mapped[int | None] = mapped_column(Integer)
    pollster: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[object | None] = mapped_column(Date)
    end_date: Mapped[object | None] = mapped_column(Date)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    population: Mapped[str | None] = mapped_column(String(100))
    party: Mapped[str] = mapped_column(String(50), nullable=False)
    pct: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "poll_id", "question_id", "party",
            name="uq_historical_generic_response"
        ),
        CheckConstraint(
            "pct >= 0 AND pct <= 100",
            name="ck_historical_generic_pct"
        ),
        CheckConstraint(
        "sample_size > 50 AND sample_size <= 100000",
        name="reasonable_sample_size"
        ),
    )



class PresidentialResult(Base):
    __tablename__ = "presidential_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    election_year: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    state_code: Mapped[str | None] = mapped_column(String(2))
    candidate: Mapped[str | None] = mapped_column(String(200))
    party: Mapped[str] = mapped_column(String(50), nullable=False)
    candidate_votes: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    total_votes: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "candidate_votes >= 0 AND total_votes >= 0",
            name="ck_presidential_votes"
        ),
        UniqueConstraint(
            "election_year",
            "state",
            "party",
            name="uq_presidential_year_state_party",
        ),
    )
