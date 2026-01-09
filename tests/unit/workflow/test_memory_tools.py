"""Unit tests for memory tools."""

from unittest.mock import MagicMock, patch

from π.workflow.memory_tools import MemoryTools, search_memories, store_memory


class TestMemoryTools:
    """Tests for MemoryTools class."""

    def test_store_memory_success(self):
        mock_memory = MagicMock()
        tools = MemoryTools(mock_memory)
        tools.user_id = "test_repo"

        result = tools.store_memory("Test lesson", "lesson_learned")

        assert "Stored:" in result
        mock_memory.add.assert_called_once()
        call_args = mock_memory.add.call_args
        assert "[lesson_learned]" in call_args[0][0]

    def test_store_memory_error(self):
        mock_memory = MagicMock()
        mock_memory.add.side_effect = Exception("Connection failed")
        tools = MemoryTools(mock_memory)
        tools.user_id = "test_repo"

        result = tools.store_memory("Test", "blocker")

        assert "Error" in result

    def test_search_returns_formatted_results(self):
        mock_memory = MagicMock()
        mock_memory.search.return_value = {
            "results": [{"memory": "[insight] Test content"}]
        }
        tools = MemoryTools(mock_memory)
        tools.user_id = "test_repo"

        result = tools.search_memories("test")

        assert "Relevant memories:" in result
        assert "Test content" in result

    def test_search_no_results(self):
        mock_memory = MagicMock()
        mock_memory.search.return_value = {"results": []}
        tools = MemoryTools(mock_memory)
        tools.user_id = "test_repo"

        result = tools.search_memories("nonexistent")

        assert "No relevant memories" in result

    def test_search_error(self):
        mock_memory = MagicMock()
        mock_memory.search.side_effect = Exception("Search failed")
        tools = MemoryTools(mock_memory)
        tools.user_id = "test_repo"

        result = tools.search_memories("query")

        assert "Error" in result

    def test_get_all_memories(self):
        mock_memory = MagicMock()
        mock_memory.get_all.return_value = {
            "results": [
                {"memory": "[lesson_learned] First lesson"},
                {"memory": "[blocker] A blocker"},
            ]
        }
        tools = MemoryTools(mock_memory)
        tools.user_id = "test_repo"

        result = tools.get_all_memories()

        assert "Memories (2):" in result
        assert "First lesson" in result

    def test_get_all_memories_empty(self):
        mock_memory = MagicMock()
        mock_memory.get_all.return_value = {"results": []}
        tools = MemoryTools(mock_memory)
        tools.user_id = "test_repo"

        result = tools.get_all_memories()

        assert "No memories stored" in result

    def test_get_all_memories_error(self):
        mock_memory = MagicMock()
        mock_memory.get_all.side_effect = Exception("Get failed")
        tools = MemoryTools(mock_memory)
        tools.user_id = "test_repo"

        result = tools.get_all_memories()

        assert "Error" in result


class TestModuleFunctions:
    """Tests for module-level DSPy tool functions."""

    @patch("π.workflow.memory_tools.get_memory_tools")
    def test_store_memory_delegates(self, mock_get_tools):
        mock_tools = MagicMock()
        mock_get_tools.return_value = mock_tools

        store_memory("test content", "insight")

        mock_tools.store_memory.assert_called_once_with("test content", "insight")

    @patch("π.workflow.memory_tools.get_memory_tools")
    def test_search_memories_delegates(self, mock_get_tools):
        mock_tools = MagicMock()
        mock_get_tools.return_value = mock_tools

        search_memories("query", 10)

        mock_tools.search_memories.assert_called_once_with("query", 10)


class TestRepoIdDetection:
    """Tests for repo ID detection."""

    @patch("π.workflow.memory_tools.subprocess.run")
    def test_get_repo_id_from_git(self, mock_run):
        # Clear the cache
        from π.workflow.memory_tools import _get_repo_id

        _get_repo_id.cache_clear()

        mock_run.return_value = MagicMock(stdout="/Users/test/Code/my-repo\n")

        result = _get_repo_id()

        assert result == "my-repo"
        _get_repo_id.cache_clear()

    @patch("π.workflow.memory_tools.subprocess.run")
    def test_get_repo_id_fallback_on_error(self, mock_run):
        from π.workflow.memory_tools import _get_repo_id

        _get_repo_id.cache_clear()

        mock_run.side_effect = Exception("Not a git repo")

        result = _get_repo_id()

        assert result == "default_repo"
        _get_repo_id.cache_clear()
