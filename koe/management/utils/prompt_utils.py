def prompt_for_object(question, objects, attr="name"):
    id2obj = {o.id: o for o in objects}
    option_lines = ["\tId: {} - {}: {}".format(obj.id, attr, getattr(obj, attr)) for obj in objects]
    acceptable_choices = [obj.id for obj in objects]
    prompt = "\n".join(option_lines) + "\nYour choice: "

    print(question)
    choice = None
    while choice is None:
        choice = input(prompt)
        try:
            choice_int = int(choice)
            assert choice_int == float(choice)
            assert choice_int in acceptable_choices
            choice = choice_int
        except Exception:
            print("Invalid option: {}".format(choice))
            choice = None
    return id2obj[choice]
