import { FC } from "react";

interface Props {
  onReset: () => void;
  onSave: () => void;
}

export const Navbar: FC<Props> = ({ onReset, onSave }) => {
  return (
    <div className="flex h-[50px] sm:h-[60px] border-b border-neutral-300 py-2 px-4 sm:px-8 items-center justify-between">
      <div className="flex items-center">
        <a
          className="text-xl sm:text-3xl font-bold hover:opacity-50"
          href="https://github.com/v2rockets/Loyal-Elephie"
        >
          🐘 Loyal Elephie
        </a>
      </div>
      <div className="flex flex-row items-center">
        <button
          className="text-sm sm:text-base text-neutral-900 font-semibold rounded-lg px-3 sm:px-4 py-1.5 sm:py-2 bg-neutral-200 hover:bg-neutral-300 focus:outline-none focus:ring-1 focus:ring-neutral-300 mr-2 sm:mr-3"
          onClick={onReset}
        >
          Reset
        </button>
        <button
          className="text-sm sm:text-base text-neutral-900 font-semibold rounded-lg px-3 sm:px-4 py-1.5 sm:py-2 bg-neutral-200 hover:bg-neutral-300 focus:outline-none focus:ring-1 focus:ring-neutral-300"
          onClick={onSave}
        >
          Save
        </button>
      </div>
    </div>
  );
}