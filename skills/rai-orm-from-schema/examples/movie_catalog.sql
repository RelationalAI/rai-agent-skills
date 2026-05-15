-- examples/movie_catalog.sql
-- Canonical small example for the SRP. Exercises:
--   - Entity types from PK tables (Movie, Director, Actor)
--   - 1:n FK fact type (Movie directed_by Director)
--   - Objectified m:n binary (Movie has Actor with character_name attribute)
--   - Object-type value enumeration via CHECK (rating)
--   - Mandatory roles via NOT NULL

CREATE TABLE DIRECTOR (
    DIRECTOR_ID  INTEGER       PRIMARY KEY,
    NAME         VARCHAR(200)  NOT NULL UNIQUE
);

CREATE TABLE ACTOR (
    ACTOR_ID     INTEGER       PRIMARY KEY,
    NAME         VARCHAR(200)  NOT NULL UNIQUE
);

CREATE TABLE MOVIE (
    MOVIE_ID      INTEGER       PRIMARY KEY,
    TITLE         VARCHAR(500)  NOT NULL,
    RELEASE_YEAR  INTEGER       NOT NULL CHECK (RELEASE_YEAR BETWEEN 1888 AND 2100),
    RATING        VARCHAR(10)   NOT NULL CHECK (RATING IN ('G','PG','PG-13','R','NC-17')),
    DIRECTOR_ID   INTEGER       NOT NULL REFERENCES DIRECTOR(DIRECTOR_ID)
);

CREATE TABLE MOVIE_ACTOR (
    MOVIE_ID         INTEGER       NOT NULL REFERENCES MOVIE(MOVIE_ID),
    ACTOR_ID         INTEGER       NOT NULL REFERENCES ACTOR(ACTOR_ID),
    CHARACTER_NAME   VARCHAR(200)  NOT NULL,
    PRIMARY KEY (MOVIE_ID, ACTOR_ID)
);
