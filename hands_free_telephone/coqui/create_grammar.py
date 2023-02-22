import random
import re
from os import write
from typing import Set, List

NAME = '{name}'
PHONE_NUMBER = '{phone_number}'


def __comments_or_empty_lines__(text: str) -> bool:
    return not (len(text.strip()) > 0 and not text.startswith('#'))


def __expand__(replace: str, replacements: List[str], inputs: Set[str]) -> Set[str]:
    new_inputs = set()
    for _input in inputs:
        if replace in _input:
            for item in replacements:
                if not __comments_or_empty_lines__(item):
                    new_inputs.add(_input.replace(replace, item))
        else:
            if not __comments_or_empty_lines__(_input):
                new_inputs.add(_input)
    return new_inputs


ALTERNATIVE = ' | '


def terminal(terminals: List[str]) -> List[str]:
    return [t.strip() for t in terminals if t.strip()]


def main():
    with open('data/keywords.txt', 'r') as keywords_file:
        keywords = keywords_file.readlines()
    with open('data/corpus.txt', 'r') as corpus_file:
        utterances = corpus_file.readlines()
    with open('data/numbers.txt', 'r') as numbers_file:
        numbers = numbers_file.readlines()
    with open('data/names.txt', 'r') as names_file:
        names = names_file.readlines()

    name_grammar = ALTERNATIVE.join(terminal(names))
    number_grammar = ALTERNATIVE.join(terminal(numbers))
    number_grammar = 'DIGIT | plus | ' + number_grammar
    keyword_grammar = ALTERNATIVE.join(terminal(keywords))

    # utterances = terminal(utterances)
    utterances = __expand__(' ' + NAME + ' ', [' $name '], utterances)
    utterances = __expand__(NAME + ' ', ['$name '], utterances)
    utterances = __expand__(' ' + NAME, [' $name'], utterances)

    utterances = __expand__(' ' + PHONE_NUMBER + ' ', [' $nummer '], utterances)
    utterances = __expand__(PHONE_NUMBER + ' ', ['$nummer '], utterances)
    utterances = __expand__(' ' + PHONE_NUMBER, [' $nummer'], utterances)

    utterances_grammar = ALTERNATIVE.join(utterances)

    inputs = []

    inputs.append('#ABNF 1.0 UTF-8;\n')
    inputs.append('language de-DE;\n')
    inputs.append('mode voice;\n')
    inputs.append('root $aussagen;\n')

    inputs.append('$aussagen = $keyword (' + utterances_grammar + ');\n')
    inputs.append('$nummer = (' + number_grammar + ')<1-15>;\n')
    inputs.append('$name = (' + name_grammar + ')<1-5>;\n')
    inputs.append('$keyword = ' + keyword_grammar + ';\n')

    with open('grammar.txt', 'w+') as input_file:
        input_file.writelines(inputs)


if __name__ == '__main__':
    main()
