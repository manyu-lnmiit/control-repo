from context_compactor.tokenizer import SimpleTokenizer, get_default_tokenizer


def test_empty_string_zero_tokens():
    assert SimpleTokenizer().count("") == 0


def test_whitespace_only_zero_tokens():
    assert SimpleTokenizer().count("   \n\t  ") == 0


def test_short_word_at_least_one_token():
    assert SimpleTokenizer().count("hi") == 1


def test_longer_text_scales_with_length():
    short = SimpleTokenizer().count("hello world")
    long = SimpleTokenizer().count("hello world " * 50)
    assert long > short * 10


def test_get_default_tokenizer_without_tiktoken_falls_back():
    tok = get_default_tokenizer(prefer_tiktoken=False)
    assert isinstance(tok, SimpleTokenizer)


def test_get_default_tokenizer_prefer_tiktoken_still_returns_working_tokenizer():
    # Whether or not tiktoken is installed in the test environment, this must
    # return something that can count tokens without raising.
    tok = get_default_tokenizer(prefer_tiktoken=True)
    assert tok.count("hello") >= 1
