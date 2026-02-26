import { Component, ElementRef, Input, ViewChild } from '@angular/core';
import { FormGroup, ReactiveFormsModule } from '@angular/forms';

@Component({
  selector: 'app-player-search-input',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './player-search-input.component.html',
  styleUrl: './player-search-input.component.scss',
})
export class PlayerSearchInputComponent {
  @Input({ required: true }) formGroup!: FormGroup;
  @Input() namePlaceholder = 'Player Name';
  @Input() tagPlaceholder = 'EUW';

  @ViewChild('tagInput') tagInputRef!: ElementRef<HTMLInputElement>;

  onNameInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const value = input.value;
    if (value.includes('#')) {
      const [name, tag] = value.split('#');
      input.value = name; // Remove # from name field immediately
      this.formGroup.patchValue({
        gameName: name,
        tagLine: tag ?? '',
      });
      setTimeout(() => this.tagInputRef?.nativeElement?.focus(), 0);
    }
  }
}
