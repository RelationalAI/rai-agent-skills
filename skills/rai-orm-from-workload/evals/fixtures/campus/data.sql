INSERT INTO DEPARTMENT VALUES ('MATH','Mathematics'),('PHYS','Physics'),('HIST','History'),('BIOL','Biology');

INSERT INTO STUDENT VALUES
 (1001,'Ada Reyes','MATH'),(1002,'Ben Okoro','MATH'),(1003,'Cleo Marsh','PHYS'),(1004,'Dev Anand','PHYS'),
 (1005,'Eli Novak','HIST'),(1006,'Fay Lindqvist','HIST'),(1007,'Gus Tanaka','BIOL'),(1008,'Hana Petrov','BIOL'),
 (1009,'Ivo Castel','MATH'),(1010,'Jun Abara','PHYS'),(1011,'Kai Morrow','HIST'),(1012,'Lia Fontaine',NULL);

-- Directory: 9 of the 12 registered students, plus nobody else. No primary key.
INSERT INTO STUDENT_DIRECTORY VALUES
 (1001,'ada@campus.example','555-0101'),(1002,'ben@campus.example','555-0102'),(1003,'cleo@campus.example',NULL),
 (1004,'dev@campus.example','555-0104'),(1005,'eli@campus.example','555-0105'),(1007,'gus@campus.example',NULL),
 (1008,'hana@campus.example','555-0108'),(1010,'jun@campus.example','555-0110'),(1011,'kai@campus.example','555-0111');

INSERT INTO STAFF VALUES
 (1,'Prof. Imani Clarke','MATH'),(2,'Dr. Tomas Weller','MATH'),(3,'Prof. Noor Haddad','PHYS'),
 (4,'Dr. Sven Aaltonen','HIST'),(5,'Dr. Rosa Dimitriou','BIOL'),(6,'Dr. Yuki Brandt','BIOL');

INSERT INTO SUBJECT VALUES
 (10,'Calculus','UG','MATH'),(11,'Topology','PG','MATH'),(12,'Mechanics','UG','PHYS'),
 (13,'Quantum Fields','PG','PHYS'),(14,'Modern History','UG','HIST'),(15,'Genetics','UG','BIOL');

INSERT INTO ENROLLMENT VALUES
 (1001,10,'2024A',72),(1001,11,'2024B',64),(1002,10,'2024A',45),(1002,12,'2024A',58),
 (1003,12,'2024A',81),(1003,13,'2024B',49),(1004,12,'2024A',38),(1004,13,'2024B',77),
 (1005,14,'2024A',66),(1006,14,'2024A',52),(1006,10,'2024B',41),(1007,15,'2024A',90),
 (1008,15,'2024A',47),(1008,14,'2024B',59),(1009,10,'2024A',88),(1009,11,'2024B',71),
 (1010,12,'2024B',55),(1010,13,'2024B',62),(1011,14,'2024B',30),(1012,15,'2024B',68);
