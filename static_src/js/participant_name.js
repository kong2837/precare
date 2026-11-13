(() => {
    const form = document.getElementById('participantNameForm');
    if (!form) return;
    form.addEventListener('submit', event => {
        // Block submission before reading inputs so an error cannot skip confirmation.
        event.preventDefault();
        const name = form.elements.namedItem('name');
        const oldName = form.elements.namedItem('old_name');
        const confirmed = form.elements.namedItem('confirmed');
        confirmed.value = '';
        const newName = name.value.trim();
        if (!newName || newName === oldName.value) {
            window.alert(newName ? '기존 이름과 동일합니다.' : '이름을 입력해주세요.');
            return;
        }
        if (!window.confirm(`이대로 이름을 변경할까요?\n\n'${oldName.value}' -> '${newName}'`)) return;
        name.value = newName;
        confirmed.value = 'yes';
        HTMLFormElement.prototype.submit.call(form);
    });
})();
