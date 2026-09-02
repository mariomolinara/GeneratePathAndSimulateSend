--
-- PostgreSQL database dump
--

-- Dumped from database version 16.4 (Debian 16.4-1.pgdg110+2)
-- Dumped by pg_dump version 16.4 (Debian 16.4-1.pgdg110+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: routes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.routes (
    id character varying(50) NOT NULL,
    short_name character varying(20) NOT NULL,
    long_name character varying(200),
    description text,
    color character varying(6),
    text_color character varying(6),
    active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Data for Name: routes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.routes (id, short_name, long_name, description, color, text_color, active, created_at) FROM stdin;
LINEA_1	18	Anello Folcara / Ausonia	Giro completo da P.za San Benedetto	5B13EC	FFFFFF	t	2026-08-31 14:05:42.847103+00
LINEA_2	19	Anello Liceo / Giardinetti	Giro completo da P.za San Benedetto	6B4E0F	FFFFFF	t	2026-08-31 14:05:42.847103+00
LINEA_2_LIC	20	Liceo Scientifico -> P.za San Benedetto	Mezza corsa: da Liceo al capolinea	0090FF	111111	t	2026-08-31 14:05:42.847103+00
LINEA_3	21	Anello Ospedali / XX Settembre	Giro completo da P.za San Benedetto	006B99	FFFFFF	t	2026-08-31 14:05:42.847103+00
LINEA_01	01	Solfegna - Casilina Nord	Orario in vigore dal 11/09/2024	D92B1E	FFFFFF	t	2026-08-31 14:05:43.0449+00
LINEA_02	02	San Cesareo - Rocca d'Evandro	Orario in vigore dal 11/09/2024	1E6720	FFFFFF	t	2026-08-31 14:05:43.0449+00
LINEA_03	03	Sant'Angelo - Panaccioni - Filaro	Orario in vigore dal 11/09/2024	DD00FF	111111	t	2026-08-31 14:05:43.0449+00
LINEA_04	04	Folcara	Orario in vigore dal 11/09/2024	8A7500	111111	t	2026-08-31 14:05:43.0449+00
LINEA_05	05	Cerro - Ponte a Cavallo	Orario in vigore dal 11/09/2024	0056D6	FFFFFF	t	2026-08-31 14:05:43.0449+00
LINEA_07	07	Cappella Morrone	Orario in vigore dal 11/09/2024	8C3B1E	FFFFFF	t	2026-08-31 14:05:43.0449+00
LINEA_08	08	Campo dei Monaci	Orario in vigore dal 11/09/2024	0B8E3F	111111	t	2026-08-31 14:05:43.0449+00
LINEA_10	10	Ospedale - Capo d'Acqua	Orario in vigore dal 11/09/2024	8E0B74	FFFFFF	t	2026-08-31 14:05:43.0449+00
LINEA_11L	11	Liceo Scientifico	Orario in vigore dal 11/09/2024	5B671E	FFFFFF	t	2026-08-31 14:05:43.0449+00
LINEA_14	14	Colle Canne	Orario in vigore dal 11/09/2024	EB6600	111111	t	2026-08-31 14:05:43.0449+00
LINEA_16	16	Universita Folcara	Orario in vigore dal 11/09/2024	147155	FFFFFF	t	2026-08-31 14:05:43.0449+00
LINEA_17	17	Ospedale	Orario in vigore dal 11/09/2024	529900	111111	t	2026-08-31 14:05:43.0449+00
LINEA_AGR	09	Istituto Agrario	Orario in vigore dal 11/09/2024	FF006E	111111	t	2026-08-31 14:05:43.0449+00
LINEA_11I	12	ITIS	Orario in vigore dal 11/09/2024	049EA9	111111	t	2026-08-31 14:05:43.0449+00
LINEA_2_LIC_R	20	Liceo Scientifico -> P.za San Benedetto (ritorno)	Mezza corsa: da Liceo al capolinea	0090FF	111111	t	2026-08-31 14:05:43.978754+00
LINEA_01_R	01	Solfegna - Casilina Nord (ritorno)	Orario in vigore dal 11/09/2024	D92B1E	FFFFFF	t	2026-08-31 14:05:43.978754+00
LINEA_02_R	02	San Cesareo - Rocca d'Evandro (ritorno)	Orario in vigore dal 11/09/2024	1E6720	FFFFFF	t	2026-08-31 14:05:43.978754+00
LINEA_04_R	04	Folcara (ritorno)	Orario in vigore dal 11/09/2024	8A7500	111111	t	2026-08-31 14:05:43.978754+00
LINEA_05_R	05	Cerro - Ponte a Cavallo (ritorno)	Orario in vigore dal 11/09/2024	0056D6	FFFFFF	t	2026-08-31 14:05:43.978754+00
LINEA_07_R	07	Cappella Morrone (ritorno)	Orario in vigore dal 11/09/2024	8C3B1E	FFFFFF	t	2026-08-31 14:05:43.978754+00
LINEA_08_R	08	Campo dei Monaci (ritorno)	Orario in vigore dal 11/09/2024	0B8E3F	111111	t	2026-08-31 14:05:43.978754+00
LINEA_10_R	10	Ospedale - Capo d'Acqua (ritorno)	Orario in vigore dal 11/09/2024	8E0B74	FFFFFF	t	2026-08-31 14:05:43.978754+00
LINEA_11L_R	11	Liceo Scientifico (ritorno)	Orario in vigore dal 11/09/2024	5B671E	FFFFFF	t	2026-08-31 14:05:43.978754+00
LINEA_16_R	16	Universita Folcara (ritorno)	Orario in vigore dal 11/09/2024	147155	FFFFFF	t	2026-08-31 14:05:43.978754+00
LINEA_AGR_R	09	Istituto Agrario (ritorno)	Orario in vigore dal 11/09/2024	FF006E	111111	t	2026-08-31 14:05:43.978754+00
LINEA_11I_R	12	ITIS (ritorno)	Orario in vigore dal 11/09/2024	049EA9	111111	t	2026-08-31 14:05:43.978754+00
\.


--
-- Name: routes routes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT routes_pkey PRIMARY KEY (id);


--
-- Name: routes trg_version_routes; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_version_routes AFTER INSERT OR DELETE OR UPDATE ON public.routes FOR EACH STATEMENT EXECUTE FUNCTION public.bump_data_version();


--
-- PostgreSQL database dump complete
--

