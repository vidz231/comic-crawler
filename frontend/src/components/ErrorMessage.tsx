import { AlertCircle } from 'lucide-react';
import './ErrorMessage.css';

interface Props {
  message?: string;
}

export default function ErrorMessage({ message = 'Something went wrong. Please try again.' }: Props) {
  return (
    <div className="error-msg" role="alert">
      <AlertCircle size={20} aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
