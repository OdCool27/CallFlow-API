-- ============================================
-- CallFlow API
-- SQL Server / T-SQL Practice Script
-- ============================================


-- ============================================
-- 1. AGENT CALL SUMMARY
-- Demonstrates:
-- LEFT JOIN
-- COUNT
-- GROUP BY
-- ============================================

SELECT
    a.id AS agent_id,
    a.name AS agent_name,
    COUNT(c.id) AS total_calls
FROM agents a
LEFT JOIN calls c
    ON a.id = c.agent_id
GROUP BY
    a.id,
    a.name
ORDER BY
    total_calls DESC;


-- ============================================
-- 2. AVERAGE CALL DURATION PER AGENT
-- Demonstrates:
-- JOIN
-- DATEDIFF
-- AVG
-- GROUP BY
-- ============================================

SELECT
    a.id AS agent_id,
    a.name AS agent_name,
    COUNT(c.id) AS completed_calls,
    AVG(
        CAST(
            DATEDIFF(
                SECOND,
                c.started_at,
                c.ended_at
            ) AS FLOAT
        )
    ) AS average_call_duration_seconds
FROM agents a
INNER JOIN calls c
    ON a.id = c.agent_id
WHERE
    c.status = 'COMPLETED'
    AND c.ended_at IS NOT NULL
GROUP BY
    a.id,
    a.name;


-- ============================================
-- 3. STORED PROCEDURE:
-- Get all calls handled by an agent
-- ============================================

CREATE OR ALTER PROCEDURE GetCallsByAgent
    @AgentId INT
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        c.id,
        c.customer_id,
        cu.name AS customer_name,
        cu.phone_number,
        c.direction,
        c.status,
        c.started_at,
        c.ended_at,
        c.notes
    FROM calls c
    INNER JOIN customers cu
        ON c.customer_id = cu.id
    WHERE
        c.agent_id = @AgentId
    ORDER BY
        c.started_at DESC;
END;
GO


-- ============================================
-- 4. STORED PROCEDURE:
-- Agent statistics
-- ============================================

CREATE OR ALTER PROCEDURE GetAgentStatistics
    @AgentId INT
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        a.id AS agent_id,
        a.name AS agent_name,

        COUNT(c.id) AS total_calls,

        SUM(
            CASE
                WHEN c.status = 'COMPLETED'
                THEN 1
                ELSE 0
            END
        ) AS completed_calls,

        AVG(
            CASE
                WHEN c.ended_at IS NOT NULL
                THEN CAST(
                    DATEDIFF(
                        SECOND,
                        c.started_at,
                        c.ended_at
                    ) AS FLOAT
                )
                ELSE NULL
            END
        ) AS average_call_duration_seconds

    FROM agents a

    LEFT JOIN calls c
        ON a.id = c.agent_id

    WHERE
        a.id = @AgentId

    GROUP BY
        a.id,
        a.name;
END;
GO



-- ============================================
-- 5. STORED PROCEDURE:
-- Complete a call
-- ============================================

CREATE OR ALTER PROCEDURE CompleteCall
    @CallId INT,
    @EndedAt DATETIME2,
    @Notes NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (
        SELECT 1
        FROM calls
        WHERE id = @CallId
    )
    BEGIN
        THROW 50001, 'Call not found.', 1;
    END;

    UPDATE calls
    SET
        status = 'COMPLETED',
        ended_at = @EndedAt,
        notes = COALESCE(@Notes, notes)
    WHERE
        id = @CallId;
END;
GO



-- ============================================
-- 6. TRANSACTION EXAMPLE
-- ============================================

BEGIN TRY

    BEGIN TRANSACTION;

    UPDATE calls
    SET status = 'COMPLETED'
    WHERE id = 1;

    INSERT INTO call_logs (
        call_id,
        message
    )
    VALUES (
        1,
        'Call marked as completed'
    );

    COMMIT TRANSACTION;

END TRY

BEGIN CATCH

    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;

END CATCH;


-- ============================================
-- 6. INDEX EXAMPLES
-- ============================================

CREATE INDEX IX_calls_agent_id
ON calls(agent_id);

CREATE INDEX IX_calls_status
ON calls(status);

CREATE INDEX IX_calls_started_at
ON calls(started_at);


-- ============================================
-- 7. VIEW:
-- Completed call summary
-- ============================================

CREATE OR ALTER VIEW CompletedCallSummary
AS

SELECT
    c.id AS call_id,
    a.name AS agent_name,
    cu.name AS customer_name,
    c.direction,
    c.started_at,
    c.ended_at,
    DATEDIFF(
        SECOND,
        c.started_at,
        c.ended_at
    ) AS duration_seconds
FROM calls c
INNER JOIN agents a
    ON c.agent_id = a.id
INNER JOIN customers cu
    ON c.customer_id = cu.id
WHERE
    c.status = 'COMPLETED'
    AND c.ended_at IS NOT NULL;
GO


