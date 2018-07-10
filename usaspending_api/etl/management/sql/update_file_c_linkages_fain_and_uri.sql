-- When both FAIN and URI are populated, update File C assistance records to link to a corresponding award if there is
-- an exact match based on FAIN first. If no exact match found, check URI.
UPDATE financial_accounts_by_awards AS faba
SET
	award_id = (
		SELECT
			id
		FROM
			awards AS aw
		WHERE
			aw.fain = faba.fain
	)
WHERE
	faba.financial_accounts_by_awards_id = ANY(
		SELECT
			faba_sub.financial_accounts_by_awards_id
		FROM
			financial_accounts_by_awards AS faba_sub
		WHERE
			faba_sub.fain IS NOT NULL
			AND
			faba_sub.uri IS NOT NULL
			AND
			faba_sub.award_id IS NULL
			AND
			(
				SELECT COUNT(*)
				FROM awards AS aw_sub
				WHERE
					aw_sub.fain = faba_sub.fain
			) = 1
	);

UPDATE financial_accounts_by_awards AS faba
SET
	award_id = (
		SELECT
			id
		FROM
			awards AS aw
		WHERE
			aw.uri = faba.uri
	)
WHERE
	faba.financial_accounts_by_awards_id = ANY(
		SELECT
			faba_sub.financial_accounts_by_awards_id
		FROM
			financial_accounts_by_awards AS faba_sub
		WHERE
			faba_sub.fain IS NOT NULL
			AND
			faba_sub.uri IS NOT NULL
			AND
			faba_sub.award_id IS NULL
			AND
			(
				SELECT COUNT(*)
				FROM awards AS aw_sub
				WHERE
					aw_sub.uri = faba_sub.uri
			) = 1
	);