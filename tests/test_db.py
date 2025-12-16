# tests/test_db.py
"""Tests for deployment timeline database."""

from ots_containers import db


class TestInitDb:
    """Test database initialization."""

    def test_init_db_creates_file(self, tmp_path):
        """init_db should create the database file."""
        db_path = tmp_path / "test.db"
        assert not db_path.exists()

        db.init_db(db_path)

        assert db_path.exists()

    def test_init_db_is_idempotent(self, tmp_path):
        """init_db should be safe to call multiple times."""
        db_path = tmp_path / "test.db"

        db.init_db(db_path)
        db.init_db(db_path)  # Should not raise

        assert db_path.exists()

    def test_init_db_creates_parent_dirs(self, tmp_path):
        """init_db should create parent directories."""
        db_path = tmp_path / "subdir" / "test.db"

        db.init_db(db_path)

        assert db_path.exists()


class TestRecordDeployment:
    """Test deployment recording."""

    def test_record_deployment_returns_id(self, tmp_path):
        """record_deployment should return the new deployment ID."""
        db_path = tmp_path / "test.db"

        deployment_id = db.record_deployment(
            db_path,
            image="ghcr.io/test/image",
            tag="v1.0.0",
            action="deploy",
            port=7043,
        )

        assert deployment_id == 1

    def test_record_deployment_increments_id(self, tmp_path):
        """Each deployment should get a new ID."""
        db_path = tmp_path / "test.db"

        id1 = db.record_deployment(db_path, "img", "v1", "deploy")
        id2 = db.record_deployment(db_path, "img", "v2", "deploy")
        id3 = db.record_deployment(db_path, "img", "v3", "deploy")

        assert id1 == 1
        assert id2 == 2
        assert id3 == 3


class TestGetDeployments:
    """Test deployment history retrieval."""

    def test_get_deployments_returns_list(self, tmp_path):
        """get_deployments should return a list of Deployment objects."""
        db_path = tmp_path / "test.db"
        db.record_deployment(db_path, "img", "v1", "deploy", port=7043)

        deployments = db.get_deployments(db_path)

        assert len(deployments) == 1
        assert deployments[0].image == "img"
        assert deployments[0].tag == "v1"
        assert deployments[0].port == 7043

    def test_get_deployments_respects_limit(self, tmp_path):
        """get_deployments should respect the limit parameter."""
        db_path = tmp_path / "test.db"
        for i in range(10):
            db.record_deployment(db_path, "img", f"v{i}", "deploy")

        deployments = db.get_deployments(db_path, limit=5)

        assert len(deployments) == 5

    def test_get_deployments_filters_by_port(self, tmp_path):
        """get_deployments should filter by port when specified."""
        db_path = tmp_path / "test.db"
        db.record_deployment(db_path, "img", "v1", "deploy", port=7043)
        db.record_deployment(db_path, "img", "v2", "deploy", port=7044)
        db.record_deployment(db_path, "img", "v3", "deploy", port=7043)

        deployments = db.get_deployments(db_path, port=7043)

        assert len(deployments) == 2
        assert all(d.port == 7043 for d in deployments)


class TestImageAliases:
    """Test image alias management."""

    def test_set_alias_creates_alias(self, tmp_path):
        """set_alias should create a new alias."""
        db_path = tmp_path / "test.db"

        db.set_alias(db_path, "CURRENT", "img", "v1.0.0")

        alias = db.get_alias(db_path, "CURRENT")
        assert alias is not None
        assert alias.image == "img"
        assert alias.tag == "v1.0.0"

    def test_set_alias_updates_existing(self, tmp_path):
        """set_alias should update an existing alias."""
        db_path = tmp_path / "test.db"

        db.set_alias(db_path, "CURRENT", "img", "v1.0.0")
        db.set_alias(db_path, "CURRENT", "img", "v2.0.0")

        alias = db.get_alias(db_path, "CURRENT")
        assert alias is not None
        assert alias.tag == "v2.0.0"

    def test_get_alias_returns_none_if_not_found(self, tmp_path):
        """get_alias should return None if alias doesn't exist."""
        db_path = tmp_path / "test.db"
        db.init_db(db_path)

        alias = db.get_alias(db_path, "NONEXISTENT")

        assert alias is None

    def test_get_all_aliases(self, tmp_path):
        """get_all_aliases should return all aliases."""
        db_path = tmp_path / "test.db"
        db.set_alias(db_path, "CURRENT", "img", "v1")
        db.set_alias(db_path, "ROLLBACK", "img", "v0")

        aliases = db.get_all_aliases(db_path)

        assert len(aliases) == 2


class TestSetCurrent:
    """Test set_current functionality."""

    def test_set_current_first_time(self, tmp_path):
        """set_current should set CURRENT when no previous exists."""
        db_path = tmp_path / "test.db"

        previous = db.set_current(db_path, "img", "v1.0.0")

        assert previous is None
        current = db.get_current_image(db_path)
        assert current == ("img", "v1.0.0")

    def test_set_current_moves_previous_to_rollback(self, tmp_path):
        """set_current should move previous CURRENT to ROLLBACK."""
        db_path = tmp_path / "test.db"

        db.set_current(db_path, "img", "v1.0.0")
        previous = db.set_current(db_path, "img", "v2.0.0")

        assert previous == "v1.0.0"
        rollback = db.get_rollback_image(db_path)
        assert rollback == ("img", "v1.0.0")


class TestRollback:
    """Test rollback functionality."""

    def test_rollback_returns_none_when_no_history(self, tmp_path):
        """rollback should return None when no previous deployment."""
        db_path = tmp_path / "test.db"
        db.init_db(db_path)

        result = db.rollback(db_path)

        assert result is None

    def test_rollback_returns_none_with_single_deployment(self, tmp_path):
        """rollback should return None when only one deployment exists."""
        db_path = tmp_path / "test.db"

        # Only one deployment - can't roll back
        db.record_deployment(db_path, "img", "v1", "deploy", port=7043)
        db.set_alias(db_path, "CURRENT", "img", "v1")

        result = db.rollback(db_path)

        assert result is None

    def test_rollback_returns_previous_deployment(self, tmp_path):
        """rollback should return the previous deployment."""
        db_path = tmp_path / "test.db"

        # Create deployment history with two DIFFERENT tags
        # First deployment
        db.record_deployment(db_path, "img", "v1", "deploy", port=7043)
        db.set_alias(db_path, "CURRENT", "img", "v1")

        # Second deployment with different tag
        db.record_deployment(db_path, "img", "v2", "deploy", port=7043)
        db.set_alias(db_path, "CURRENT", "img", "v2")
        db.set_alias(db_path, "ROLLBACK", "img", "v1")

        # Rollback should go from v2 to v1
        result = db.rollback(db_path)

        # Result is the tag we rolled back TO
        assert result == ("img", "v1")

    def test_rollback_updates_aliases(self, tmp_path):
        """rollback should update CURRENT and ROLLBACK aliases."""
        db_path = tmp_path / "test.db"

        # Create deployment history
        db.record_deployment(db_path, "img", "v1", "deploy")
        db.set_alias(db_path, "CURRENT", "img", "v1")

        db.record_deployment(db_path, "img", "v2", "deploy")
        db.set_alias(db_path, "CURRENT", "img", "v2")
        db.set_alias(db_path, "ROLLBACK", "img", "v1")

        db.rollback(db_path)

        current = db.get_current_image(db_path)
        rollback = db.get_rollback_image(db_path)

        # After rollback: v1 is current, v2 is rollback
        assert current == ("img", "v1")
        assert rollback == ("img", "v2")


class TestGetPreviousTags:
    """Test get_previous_tags functionality."""

    def test_get_previous_tags_returns_distinct(self, tmp_path):
        """get_previous_tags should return distinct image/tag pairs."""
        db_path = tmp_path / "test.db"

        db.record_deployment(db_path, "img", "v1", "deploy")
        db.record_deployment(db_path, "img", "v1", "redeploy")  # Same tag
        db.record_deployment(db_path, "img", "v2", "deploy")

        tags = db.get_previous_tags(db_path)

        # Should have 2 distinct tags
        tag_values = [t[1] for t in tags]
        assert "v1" in tag_values
        assert "v2" in tag_values
