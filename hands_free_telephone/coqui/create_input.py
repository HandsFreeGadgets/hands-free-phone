import random
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
                    new_inputs.add(__replace_umlauts__(_input.replace(replace, item.strip())))
        else:
            if not __comments_or_empty_lines__(_input):
                new_inputs.add(__replace_umlauts__(_input))
    return new_inputs


def __replace_umlauts__(text: str) -> str:
    return text.replace("ü", "ue").replace("ä", "ae").replace("ö", "oe").replace("ß", "ss")


def __create_phone_number__(numbers: List[str], lower: int = 3, higher: int = 10) -> str:
    return ('plus ' if bool(random.getrandbits(1)) else '') + ' '.join(
        random.choices(list(map(lambda x: x.strip(), numbers[1:11])), k=random.randrange(lower, higher))).strip()


def main():
    with open('data/keywords.txt', 'r') as keywords_file:
        keywords = keywords_file.readlines()
    with open('data/corpus.txt', 'r') as corpus_file:
        utterances = corpus_file.readlines()
    with open('data/numbers.txt', 'r') as numbers_file:
        numbers = numbers_file.readlines()
    with open('data/names.txt', 'r') as names_file:
        names = names_file.readlines()
    # create a set of phone number from numbers
    with open('data/phonenumbers.txt', 'w+') as phone_numbers_file:
        for i in range(100):
            number = __create_phone_number__(numbers, higher=13)
            phone_numbers_file.write(number + '\n')
        for i in range(100):
            phone_numbers_file.write(__create_phone_number__(numbers, lower=5) + '\n')
    with open('data/phonenumbers.txt', 'r') as phone_numbers_file:
        phone_numbers = phone_numbers_file.readlines()

    inputs = set()

    for utterance in utterances:
        for keyword in keywords:
            inputs.add(keyword.strip() + ' ' + utterance)

    inputs = __expand__(NAME, names, inputs)
    inputs = __expand__(PHONE_NUMBER, phone_numbers, inputs)

    with open('input.txt', 'w+') as input_file:
        input_file.writelines(inputs)


if __name__ == '__main__':
    main()
