-- ============================================================
-- V5__refresh_timetable_magni.sql
-- Dati reali Magni Autoservizi (Cassino) — 3 anelli da Piazza San Benedetto.
-- Sostituisce il seed fittizio di V4 senza modificarla (no checksum mismatch).
-- Tempi-tratto presi dagli orari ufficiali; arrival_seconds derivato:
--   arrivo = partenza + somma tratti + 60s di sosta per ogni fermata intermedia.
-- ============================================================

-- 1) Nuova colonna: tempo (secondi) per arrivare a QUESTA fermata dalla precedente.
ALTER TABLE scheduled_stops
    ADD COLUMN IF NOT EXISTS travel_seconds_from_prev INTEGER;

-- 2) Pulizia dei dati precedenti (ordine: figli -> padri per via delle FK).
DELETE FROM scheduled_stops;
DELETE FROM trips;
DELETE FROM stops;
DELETE FROM routes;

-- 3) ROUTES — un anello per percorso.
INSERT INTO routes (id, short_name, long_name, description, color, text_color) VALUES
    ('LINEA_1','1','Anello Folcara / Ausonia',      'Giro completo da P.za San Benedetto','1976D2','FFFFFF'),
    ('LINEA_2','2','Anello Liceo / Giardinetti',    'Giro completo da P.za San Benedetto','E67E22','FFFFFF'),
    ('LINEA_2_LIC','2','Liceo Scientifico -> P.za San Benedetto','Mezza corsa: da Liceo al capolinea','E67E22','FFFFFF'),
    ('LINEA_3','3','Anello Ospedali / XX Settembre','Giro completo da P.za San Benedetto','27AE60','FFFFFF');

-- 4) STOPS — fermate distinte, coordinate in decimale (DMS gia' convertiti).
INSERT INTO stops (id, name, lat, lon) VALUES
    ('PSB','Piazza San Benedetto',41.493833,13.828778),
    ('CRS','C.so Repubblica',41.49046,13.83673),
    ('VLE','V.le Europa',41.48911,13.83955),
    ('VGA','Via Garigliano',41.48592,13.83505),
    ('SFF','Staz. FF.SS.',41.48546,13.83204),
    ('VBO','Viale Bonomi',41.48451,13.82781),
    ('VSA','Via Sant''angelo',41.48221,13.82569),
    ('UNI','Universita Folcara',41.47583,13.82894),
    ('RET','Rettorato',41.47179,13.82752),
    ('RLD','Residenze Lazio DiSCo',41.46939,13.82897),
    ('AUS','Via Ausonia',41.4787,13.82294),
    ('COL','Colosseo',41.4816,13.82408),
    ('IMA','Istituto Magistrale',41.4875,13.839611),
    ('EDN','Via Enrico De Nicola',41.490639,13.836639),
    ('LIC','Liceo Scientifico',41.467472,13.829139),
    ('GIA','Giardinetti',41.492,13.831472),
    ('ING','Facolta di Ingegneria',41.487361,13.825472),
    ('OSR','Ospedale San Raffaele',41.483083,13.825111),
    ('XXS','Via XX Settembre',41.494111,13.83175),
    ('OSS','Ospedale Santa Scolastica',41.505639,13.842639);

-- 5) Helper di sessione: genera trip + scheduled_stops per una linea.
--    Per ogni partenza crea un trip e percorre la sequenza accumulando
--    l'orario: nessuna sosta alla partenza, +60s ad ogni fermata intermedia.
CREATE OR REPLACE FUNCTION pg_temp.gen_line(
    p_route TEXT, p_bus1 INT, p_bus2 INT,
    p_stops TEXT[], p_legs INT[], p_deps INT[]
) RETURNS void AS $f$
DECLARE
    d INT; idx INT; i INT; tid TEXT; arr INT; tfp INT; chosen INT;
BEGIN
    FOR idx IN 1..array_length(p_deps,1) LOOP
        d := p_deps[idx];
        chosen := CASE WHEN idx % 2 = 1 THEN p_bus1 ELSE p_bus2 END;  -- alterna i due bus
        tid := p_route || '_' || d;

        INSERT INTO trips(id, route_id, bus_id) VALUES (tid, p_route, chosen);

        arr := d;
        FOR i IN 1..array_length(p_stops,1) LOOP
            IF i = 1 THEN
                tfp := 0;            arr := d;                 -- capolinea: parte qui
            ELSIF i = 2 THEN
                tfp := p_legs[i];    arr := arr + tfp;          -- primo tratto, niente sosta
            ELSE
                tfp := p_legs[i];    arr := arr + 60 + tfp;     -- sosta 60s + tratto
            END IF;

            INSERT INTO scheduled_stops(trip_id, stop_id, stop_sequence, arrival_seconds, travel_seconds_from_prev)
            VALUES (tid, p_stops[i], i, arr, tfp);
        END LOOP;
    END LOOP;
END;
$f$ LANGUAGE plpgsql;

-- 6) Generazione vera e propria.
DO $$
DECLARE
    bus1 INT; bus2 INT; bus3 INT; bus4 INT;
BEGIN
    SELECT bus_id INTO bus1 FROM buses WHERE current_vehicle_id='MAGNI-001' LIMIT 1;
    SELECT bus_id INTO bus2 FROM buses WHERE current_vehicle_id='MAGNI-002' LIMIT 1;
    SELECT bus_id INTO bus3 FROM buses WHERE current_vehicle_id='MAGNI-003' LIMIT 1;
    SELECT bus_id INTO bus4 FROM buses WHERE current_vehicle_id='MAGNI-004' LIMIT 1;
    bus2 := COALESCE(bus2,bus1); bus3 := COALESCE(bus3,bus1); bus4 := COALESCE(bus4,bus1);

    -- LINEA 1: 08:00..19:00 ogni 30 min, alterna MAGNI-001 / MAGNI-002
    PERFORM pg_temp.gen_line('LINEA_1', bus1, bus2,
        ARRAY['PSB','CRS','VLE','VGA','SFF','VBO','VSA','UNI','RET','RLD','AUS','COL','VBO','SFF','VGA','IMA','EDN','PSB'],
        ARRAY[0,240,60,60,60,60,60,120,60,60,240,60,120,60,60,60,120,180],
        ARRAY[28800,30600,32400,34200,36000,37800,39600,41400,43200,45000,46800,48600,50400,52200,54000,55800,57600,59400,61200,63000,64800,66600,68400]);

    -- LINEA 2: per ora solo la partenza 08:05 da PSB (vedi nota sotto), MAGNI-003
    PERFORM pg_temp.gen_line('LINEA_2', bus3, bus3,
        ARRAY['PSB','CRS','VLE','VGA','SFF','LIC','COL','SFF','EDN','GIA','PSB'],
        ARRAY[0,240,60,60,60,360,360,120,180,120,120],
        ARRAY[29100]);

    -- LINEA 2 (mezza corsa): partenze dal Liceo Scientifico, solo coda LIC->PSB, MAGNI-003
    PERFORM pg_temp.gen_line('LINEA_2_LIC', bus3, bus3,
        ARRAY['LIC','COL','SFF','EDN','GIA','PSB'],
        ARRAY[0,360,120,180,120,120],
        ARRAY[32400,36000,45000,48600,59400]);

    -- LINEA 3: 08:00..19:00 ogni 30 min, MAGNI-004
    PERFORM pg_temp.gen_line('LINEA_3', bus4, bus4,
        ARRAY['PSB','ING','OSR','SFF','VGA','IMA','EDN','XXS','OSS','XXS','GIA','PSB'],
        ARRAY[0,120,60,120,60,60,120,120,300,300,60,120],
        ARRAY[28800,30600,32400,34200,36000,37800,39600,41400,43200,45000,46800,48600,50400,52200,54000,55800,57600,59400,61200,63000,64800,66600,68400]);
END $$;
