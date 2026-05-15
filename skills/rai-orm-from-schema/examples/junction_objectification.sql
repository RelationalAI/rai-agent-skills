-- examples/junction_objectification.sql
-- Two junction tables in the same schema, contrasting:
--   - STUDENT_INTERESTED_IN: composite all-FK PK, no extra columns → pure m:n binary
--   - ENROLMENT: composite all-FK PK + extra columns → objectified entity
-- The SRP's Step 7 must distinguish these via the ambiguous-junction-no-extras /
-- ambiguous-junction-with-extras antipattern codes.

CREATE TABLE STUDENT (
    STUDENT_ID  INTEGER       PRIMARY KEY,
    NAME        VARCHAR(200)  NOT NULL
);

CREATE TABLE COURSE (
    COURSE_ID   INTEGER       PRIMARY KEY,
    TITLE       VARCHAR(200)  NOT NULL
);

-- Pure m:n binary: students mark "interested" in courses for a wishlist.
-- No attributes on the relationship itself.
CREATE TABLE STUDENT_INTERESTED_IN (
    STUDENT_ID  INTEGER  NOT NULL REFERENCES STUDENT(STUDENT_ID),
    COURSE_ID   INTEGER  NOT NULL REFERENCES COURSE(COURSE_ID),
    PRIMARY KEY (STUDENT_ID, COURSE_ID)
);

-- Objectified: enrolment has its own attributes (when, grade) and is naturally
-- a thing in itself, not just a connection.
CREATE TABLE ENROLMENT (
    STUDENT_ID    INTEGER     NOT NULL REFERENCES STUDENT(STUDENT_ID),
    COURSE_ID     INTEGER     NOT NULL REFERENCES COURSE(COURSE_ID),
    ENROLLED_AT   TIMESTAMP   NOT NULL,
    GRADE         VARCHAR(2)  CHECK (GRADE IN ('A','B','C','D','F','I','W')),
    PRIMARY KEY (STUDENT_ID, COURSE_ID)
);
